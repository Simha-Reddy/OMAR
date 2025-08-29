import os
from openai import AzureOpenAI
from vista_api import VistaRPCClient, VistaRPCLogger
from flask import current_app
import atexit


def init_openai(app):
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("[WARN] AZURE_OPENAI_API_KEY not set")
        return
    api_version = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
    if not endpoint:
        print("[WARN] AZURE_OPENAI_ENDPOINT not set; skipping Azure OpenAI client init")
        return
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        app.config['OPENAI_CLIENT'] = client
    except Exception as e:
        print(f"[WARN] Failed to init AzureOpenAI client: {e}")
        app.config['OPENAI_CLIENT'] = None


def init_vista(app):
    """
    Best-effort initialization from environment variables. If credentials are not
    provided, skip connecting. A user can sign in later via the login route.
    """
    host = os.getenv('VISTA_HOST')
    port_env = os.getenv('VISTA_PORT')
    try:
        port = int(port_env) if port_env else None
    except Exception:
        port = None
    access = os.getenv('VISTA_ACCESS_CODE')  # no default
    verify = os.getenv('VISTA_VERIFY_CODE')  # no default
    context = os.getenv('VISTA_RPC_CONTEXT')  # no default
    logger = VistaRPCLogger()
    # Only attempt to connect if all required values are present
    if not (host and port and access and verify and context):
        print('[INFO] VistA connection info not fully set in environment; login required on landing page.')
        app.config['VISTA_CLIENT'] = None
        return
    try:
        client = VistaRPCClient(host, port, access, verify, context, logger)
        client.connect()
        client.start_heartbeat(interval=int(os.getenv('VISTA_HEARTBEAT_INTERVAL', '30')))
        app.config['VISTA_CLIENT'] = client
        def _close_on_exit():
            try:
                c = app.config.get('VISTA_CLIENT')
                if c:
                    c.close()
            except Exception:
                pass
        atexit.register(_close_on_exit)
    except Exception as e:
        print(f"[WARN] Could not initialize VistA socket client: {e}")
        app.config['VISTA_CLIENT'] = None
    # Do NOT close the shared VistA client on each request; keep it persistent for reuse


def login_vista_with_credentials(app, site_key: str, access: str, verify: str, context: str = None):
    """
    Create and connect a VistA client using user-supplied credentials and site selection.
    Replaces any existing client in app.config['VISTA_CLIENT'].
    """
    # Map site to host/port. For now only Puget Sound via environment.
    sites = {
        'puget-sound': {
            'host': os.getenv('VISTA_HOST'),
            'port': int(os.getenv('VISTA_PORT')) if os.getenv('VISTA_PORT') else None
        }
    }
    site = sites.get((site_key or 'puget-sound').lower(), sites['puget-sound'])
    host = site.get('host')
    port = site.get('port')
    if not (host and port):
        raise RuntimeError('VistA host/port not configured. Set VISTA_HOST and VISTA_PORT in environment.')
    if not context:
        context = os.getenv('VISTA_RPC_CONTEXT') or ''
        if not context:
            raise RuntimeError('VistA RPC context not configured. Set VISTA_RPC_CONTEXT in environment or pass explicitly.')

    # Close previous client if any
    try:
        prev = app.config.get('VISTA_CLIENT')
        if prev:
            prev.close()
    except Exception:
        pass

    logger = VistaRPCLogger()
    client = VistaRPCClient(host, port, access, verify, context, logger)
    client.connect()
    client.start_heartbeat(interval=int(os.getenv('VISTA_HEARTBEAT_INTERVAL', '30')))
    app.config['VISTA_CLIENT'] = client
    return {'host': host, 'port': port}
