import os
import socket
import re
import time
import random
import threading

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- VistA Socket-based RPC Client ---

# Added: Helpers to load cipher from environment or external file

def _parse_cipher_blob(blob: str):
    """Parse cipher content from env/file. Accepts JSON list or newline-separated rows."""
    if not blob:
        return None
    txt = blob.strip()
    # Try JSON first
    try:
        import json
        data = json.loads(txt)
        if isinstance(data, list) and all(isinstance(x, str) for x in data) and len(data) >= 2:
            return data
    except Exception:
        pass
    # Fallback: splitlines
    rows = [ln for ln in txt.replace('\r','').split('\n') if ln.strip()]
    if len(rows) >= 2:
        return rows
    return None


def _load_cipher_from_env():
    """Load cipher table from VISTARPC_CIPHER or VISTARPC_CIPHER_FILE. Returns list[str] or raises."""
    path = os.getenv('VISTARPC_CIPHER_FILE')
    if path:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            parsed = _parse_cipher_blob(content)
            if parsed:
                return parsed
        except Exception:
            pass
    blob = os.getenv('VISTARPC_CIPHER')
    if blob:
        parsed = _parse_cipher_blob(blob)
        if parsed:
            return parsed
    raise RuntimeError('VISTARPC_CIPHER not configured. Set VISTARPC_CIPHER to a JSON list of rows or provide VISTARPC_CIPHER_FILE path.')


class VistaRPCLogger:
    def logInfo(self, tag, msg):
        try:
            tid = threading.get_ident()
        except Exception:
            tid = 'n/a'
        print(f"[INFO] {tag}: {msg} (tid={tid})")
    def logError(self, tag, msg):
        try:
            tid = threading.get_ident()
        except Exception:
            tid = 'n/a'
        print(f"[ERROR] {tag}: {msg} (tid={tid})")

class VistaRPCClient:
    # Load at runtime from environment for security
    CIPHER = None

    def __init__(self, host, port, access, verify, context, logger=None):
        self.host = host
        self.port = port
        self.access = access
        self.verify = verify
        self.context = context
        self.sock = None
        self.logger = logger or VistaRPCLogger()
        self.endMark = chr(4)
        self._last_used = time.time()
        # Thread-safety & heartbeat control
        self.lock = threading.RLock()
        self._hb_thread = None
        self._hb_stop = threading.Event()
        self._hb_interval = 60
        # Serialize connection lifecycle (connect/reconnect/close/handshake)
        self.conn_lock = threading.RLock()
        # Single-flight reconnect controls
        self._reconnecting = False
        self._reconnect_event = threading.Event()

    def _get_cipher(self):
        c = getattr(self.__class__, 'CIPHER', None)
        if not c:
            c = _load_cipher_from_env()
            self.__class__.CIPHER = c
        return c

    def _configure_keepalive(self, sock):
        """Enable basic TCP keepalive (fine-grained tuning OS-specific; basic works cross-platform)."""
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Platform specific tuning could be added here if necessary.
        except Exception as e:
            self.logger.logError("VistaRPCClient", f"Could not set TCP keepalive: {e}")

    def connect(self):
        # Always create a new socket for each handshake attempt
        with self.conn_lock:
            backoff = 0.5
            for attempt in range(4):
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._configure_keepalive(self.sock)
                self.sock.connect((self.host, self.port))
                self.logger.logInfo("VistaRPCClient", f"Connected to {self.host}:{self.port}")
                time.sleep(0.3 + random.random()*0.2)
                try:
                    self._handshake()  # called under conn_lock
                    return
                except Exception as e:
                    self.logger.logError("VistaRPCClient", f"Handshake attempt {attempt+1} failed: {e}")
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                    self.sock = None
                    if attempt == 3:
                        raise
                    time.sleep(backoff + random.random()*0.2)
                    backoff = min(backoff * 2, 2.0)

    def _handshake(self):
        with self.conn_lock:
            with self.lock:
                tcp_params = [socket.gethostbyname(socket.gethostname()), "0", "FMQL"]
                tcpConnect = self._makeRequest("TCPConnect", tcp_params, True)
                self.sock.send(tcpConnect.encode('utf-8'))
                connectReply = self._readToEndMarker()
                if not re.match(r'accept', connectReply):
                    raise Exception("TCPConnect failed", connectReply)
                signOn = self._makeRequest("XUS SIGNON SETUP", [])
                self.sock.send(signOn.encode('utf-8'))
                self._readToEndMarker()
                accessVerify = self._encrypt(self.access + ";" + self.verify).decode()
                login = self._makeRequest("XUS AV CODE", [accessVerify])
                self.sock.send(login.encode('utf-8'))
                connectReply = self._readToEndMarker()
                if re.search(r'Not a valid ACCESS CODE/VERIFY CODE pair', connectReply):
                    raise Exception("Login failed", connectReply)
                # Create context: try plaintext first, fallback to encrypted if site expects it
                ctx_plain = self._makeRequest("XWB CREATE CONTEXT", [self.context])
                self.sock.send(ctx_plain.encode('utf-8'))
                ctxReply = self._readToEndMarker()
                if re.search(r'Application context has not been created', ctxReply) or re.search(r'does not exist on server', ctxReply):
                    # Fallback to encrypted
                    eMSGCONTEXT = self._encrypt(self.context).decode()
                    ctx_enc = self._makeRequest("XWB CREATE CONTEXT", [eMSGCONTEXT])
                    self.sock.send(ctx_enc.encode('utf-8'))
                    ctxReply = self._readToEndMarker()
                    if re.search(r'Application context has not been created', ctxReply) or re.search(r'does not exist on server', ctxReply):
                        raise Exception("Context failed", ctxReply)
                    else:
                        self.logger.logInfo("VistaRPCClient", "Handshake complete (ctx encrypted)")
                        return
                self.logger.logInfo("VistaRPCClient", "Handshake complete")

    def _makeRequest(self, name, params, isCommand=False):
        protocoltoken = "[XWB]1130"
        commandtoken = "4" if isCommand else "2" + chr(1) + "1"
        namespec = chr(len(name)) + name
        if not params:
            paramsspecs = "54f"
        else:
            paramsspecs = "5"
            for param in params:
                if not isinstance(param, dict):
                    param_bytes = param.encode('utf-8')
                    paramsspecs += "0" + str(len(param_bytes)).zfill(3) + param
            paramsspecs += "f"
        endtoken = chr(4)
        request = protocoltoken + commandtoken + namespec + paramsspecs + endtoken
        return request

    def _readToEndMarker(self):
        msgChunks = []
        while True:
            chunk = self.sock.recv(256)
            if not chunk:
                # Socket closed unexpectedly before end marker
                raise OSError("Socket closed during read")
            msgChunk = chunk.decode('utf-8', errors='replace')
            if not len(msgChunks) and msgChunk and msgChunk[0] == "\x00":
                msgChunk = msgChunk[2:]
            if msgChunk and msgChunk[-1] == self.endMark:
                msgChunks.append(msgChunk[:-1])
                break
            msgChunks.append(msgChunk)
        return "".join(msgChunks)

    def _encrypt(self, val):
        # Encrypt a string using two randomly chosen cipher rows
        import random
        cipher = self._get_cipher()
        cipher_len = len(cipher)
        ra = random.randint(0, cipher_len - 1)
        rb = random.randint(0, cipher_len - 1)
        while rb == ra or rb == 0:
            rb = random.randint(0, cipher_len - 1)
        # Remove debug logging for production
        cra = cipher[ra]
        crb = cipher[rb]
        cval = chr(ra + 32)  # Prefix with cipher row index
        for c in val:
            index = cra.find(c)
            if index == -1:
                cval += c  # If char not found, leave as is
            else:
                cval += crb[index]  # Substitute using cipher
        cval += chr(rb + 32)  # Suffix with second cipher row index
        return cval.encode("utf-8")

    def _send_request_locked(self, name, params, isCommand=False):
        with self.lock:
            if not self.sock:
                raise OSError("Socket is not connected")
            request = self._makeRequest(name, params, isCommand)
            self.sock.send(request.encode('utf-8'))
            return self._readToEndMarker()

    def invokeRPC(self, name, params):
        """Invoke an RPC with automatic reconnect on common socket errors and single-flight reconnect coordination."""
        def _do_invoke():
            return self._send_request_locked(name, params, False)
        try:
            self._last_used = time.time()
            return _do_invoke()
        except (OSError, socket.error) as e:
            # If another thread is reconnecting, wait then retry
            if self._reconnecting:
                self.logger.logError('VistaRPCClient', f'Socket error on {name}: {e}; waiting for reconnect to complete.')
                try:
                    self._reconnect_event.wait(10)
                    self._last_used = time.time()
                    return _do_invoke()
                except Exception as e2:
                    self.logger.logError('VistaRPCClient', f'Post-wait retry failed for {name}: {e2}')
                    # fallthrough to attempt our own reconnect if reconnectable
            if self._is_reconnectable_error(e):
                self.logger.logError('VistaRPCClient', f'Socket error on invokeRPC {name}: {e}; attempting reconnect.')
                try:
                    prev_ctx = self.context
                    self.reconnect()
                    if self.context != prev_ctx:
                        try:
                            self.setContext(prev_ctx)
                        except Exception:
                            pass
                    self._last_used = time.time()
                    return _do_invoke()
                except Exception as e2:
                    self.logger.logError('VistaRPCClient', f'Reconnect attempt failed for {name}: {e2}')
                    raise
            raise

    def close(self):
        # Stop heartbeat first
        self.stop_heartbeat()
        with self.conn_lock:
            if self.sock:
                try:
                    with self.lock:
                        try:
                            self.sock.send("#BYE#".encode('utf-8'))
                        except Exception:
                            pass
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                self.sock = None

    def setContext(self, context):
        """Switch RPC context; try plaintext first, then encrypted as fallback; retries once with reconnect on errors."""
        failure_markers = ('Application context has not been created', 'does not exist on server')
        attempt = 0
        while attempt < 2:
            try:
                with self.conn_lock:
                    with self.lock:
                        if not self.sock:
                            raise OSError('Socket is not connected')
                        # Plaintext attempt
                        req_plain = self._makeRequest("XWB CREATE CONTEXT", [context])
                        self.sock.send(req_plain.encode('utf-8'))
                        reply = self._readToEndMarker()
                        if any(m in reply for m in failure_markers):
                            # Fallback to encrypted
                            enc_val = self._encrypt(context).decode()
                            req_enc = self._makeRequest("XWB CREATE CONTEXT", [enc_val])
                            self.sock.send(req_enc.encode('utf-8'))
                            reply = self._readToEndMarker()
                            if any(m in reply for m in failure_markers):
                                raise Exception(f"Context switch failed: {reply}")
                self.context = context
                self._last_used = time.time()
                self.logger.logInfo('VistaRPCClient', f'Context switched to {context}')
                return
            except (OSError, socket.error) as e:
                if self._is_reconnectable_error(e) and attempt == 0:
                    self.logger.logError('VistaRPCClient', f'Socket error during setContext {context}: {e}; reconnecting.')
                    self.reconnect()
                    attempt += 1
                    continue
                self.logger.logError('VistaRPCClient', f'Context switch socket error for {context}: {e}')
                raise
            except Exception as e:
                if attempt == 0:
                    self.logger.logError('VistaRPCClient', f'Context switch error for {context}: {e}; reconnecting.')
                    try:
                        self.reconnect()
                    except Exception:
                        pass
                    attempt += 1
                    continue
                self.logger.logError('VistaRPCClient', f'Context switch error for {context}: {e}')
                raise

    def reconnect(self):
        """Public reconnect method now uses single-flight coordination."""
        self._singleflight_reconnect()

    def ensure_connected(self, max_idle_seconds=300):
        """Optionally ping/reconnect if idle too long (call before heavy RPC); coordinates reconnects."""
        if not self.sock:
            self.reconnect()
            return
        if (time.time() - getattr(self, '_last_used', 0)) > max_idle_seconds:
            # Attempt lightweight ping
            try:
                self.invokeRPC('XUS GET USER INFO', [])
            except Exception:
                self.logger.logInfo('VistaRPCClient', 'Idle connection stale; reconnecting.')
                self.reconnect()

    def start_heartbeat(self, interval=60):
        """Start a background heartbeat thread to keep the session alive and detect drops."""
        self._hb_interval = interval
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._hb_stop.clear()
        def _runner():
            while not self._hb_stop.wait(self._hb_interval):
                try:
                    # Only ping if socket exists and was idle > 2*interval
                    if self.sock and (time.time() - self._last_used) > (self._hb_interval * 2):
                        self.logger.logInfo('VistaRPCClient', 'Heartbeat ping...')
                        self.invokeRPC('XUS GET USER INFO', [])
                except Exception as e:
                    self.logger.logError('VistaRPCClient', f'Heartbeat detected issue: {e}; reconnecting.')
                    try:
                        self.reconnect()
                    except Exception as e2:
                        self.logger.logError('VistaRPCClient', f'Heartbeat reconnect failed: {e2}')
        self._hb_thread = threading.Thread(target=_runner, name='VistaRPCHeartbeat', daemon=True)
        self._hb_thread.start()

    def stop_heartbeat(self):
        self._hb_stop.set()
        t = self._hb_thread
        self._hb_thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=2)
            except Exception:
                pass

    def _is_reconnectable_error(self, e):
        msg = str(e).lower()
        reconnect_terms = ['10053', '10054', '10057', '10038', 'connection reset', 'connection aborted', 'broken pipe', 'timed out', 'not a socket', 'not connected']
        return any(term in msg for term in reconnect_terms)

    def _singleflight_reconnect(self, timeout=15):
        """Ensure only one thread performs reconnect; others wait for it to finish."""
        # Fast-path: if a reconnect is already ongoing, wait for it
        if self._reconnecting:
            self.logger.logInfo('VistaRPCClient', 'Waiting for ongoing reconnect...')
            finished = self._reconnect_event.wait(timeout)
            if not finished:
                raise TimeoutError('Timed out waiting for reconnect')
            return
        # Become the reconnect leader
        with self.conn_lock:
            if self._reconnecting:
                # Double-check under lock
                self.logger.logInfo('VistaRPCClient', 'Waiting for ongoing reconnect (post-lock)...')
                finished = self._reconnect_event.wait(timeout)
                if not finished:
                    raise TimeoutError('Timed out waiting for reconnect')
                return
            # Mark reconnection starting
            self._reconnecting = True
            self._reconnect_event.clear()
            try:
                # Perform reconnect sequence
                try:
                    self.close()
                except Exception:
                    pass
                self.logger.logInfo('VistaRPCClient', 'Reconnecting to VistA...')
                self.connect()
            finally:
                # Signal finish
                self._reconnecting = False
                self._reconnect_event.set()

    def call_in_context(self, name, params, context):
        """Atomically ensure context then invoke RPC while holding the connection lock to prevent context races."""
        with self.conn_lock:
            if self.context != context:
                self.setContext(context)
            return self.invokeRPC(name, params)