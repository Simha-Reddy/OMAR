import os
from flask import Flask
from flask_session import Session
from dotenv import load_dotenv


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

    # Feature flags (placeholders)
    app.config['USE_VAX_GATEWAY'] = os.getenv('USE_VAX_GATEWAY', '1').lower() in ('1', 'true', 'yes', 'on')

    # Session config (Redis or FakeRedis)
    from datetime import timedelta
    def _truthy(v: str, default: str = '0') -> bool:
        s = v if v is not None else default
        return str(s).strip().lower() in ('1','true','yes','on')

    use_fakeredis = _truthy(os.getenv('USE_FAKEREDIS','1'))
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=int(os.getenv('SESSION_LIFETIME_SECONDS', '1800')))
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_SECURE'] = _truthy(os.getenv('SESSION_COOKIE_SECURE','0'))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE','Strict')

    redis_client = None
    try:
        if use_fakeredis:
            import fakeredis
            redis_client = fakeredis.FakeRedis(decode_responses=False)
        else:
            from redis import Redis
            redis_client = Redis(
                host=os.getenv('REDIS_HOST','127.0.0.1'),
                port=int(os.getenv('REDIS_PORT','6379')),
                db=int(os.getenv('REDIS_DB','0')),
                password=os.getenv('REDIS_PASSWORD') or None,
                ssl=str(os.getenv('REDIS_SSL','0')).lower() in ('1','true','yes','on'),
                decode_responses=False,
            )
            try:
                redis_client.ping()
            except Exception:
                redis_client = None
    except Exception:
        redis_client = None

    if redis_client is not None:
        app.config['SESSION_REDIS'] = redis_client
    Session(app)

    # Security headers + CSRF double-submit cookie
    from flask import request, session as flask_session, jsonify
    import secrets

    # Distinctive debug coloring so it's obvious this is the refactor server
    _USE_COLOR_BANNER = str(os.getenv('OMAR_REFACTOR_DEBUG_COLOR', '1')).strip().lower() in ('1','true','yes','on')
    _CLR_MAGENTA = "\033[95m"
    _CLR_CYAN = "\033[96m"
    _CLR_RESET = "\033[0m"
    try:
        if _USE_COLOR_BANNER:
            print(f"{_CLR_MAGENTA}[OMAR_refactor] Flask app initializing (refactor) {_CLR_RESET}")
            app.logger.info(f"{_CLR_CYAN}[OMAR_refactor] create_app ready{_CLR_RESET}")
    except Exception:
        pass

    @app.context_processor
    def _inject_csrf_token():
        return {'csrf_token': flask_session.get('csrf_token', '')}

    def _is_csrf_protected_path(path: str) -> bool:
        return True

    @app.before_request
    def _csrf_before_request():
        try:
            if 'csrf_token' not in flask_session:
                flask_session['csrf_token'] = secrets.token_urlsafe(32)
            if request.method in ('GET','HEAD','OPTIONS'):
                return None
            if _is_csrf_protected_path(request.path):
                h = request.headers.get('X-CSRF-Token')
                c = request.cookies.get('csrf_token')
                s = flask_session.get('csrf_token')
                if not h or not c or not s or h != c or h != s:
                    return jsonify({'error':'CSRF token invalid'}), 403
        except Exception:
            if request.method in ('POST','PUT','PATCH','DELETE') and _is_csrf_protected_path(request.path):
                return jsonify({'error':'CSRF validation error'}), 403
            return None

    @app.after_request
    def _security_headers(resp):
        try:
            if not request.path.startswith('/static'):
                resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
                resp.headers['Pragma'] = 'no-cache'
                resp.headers['Expires'] = '0'
                resp.headers['Vary'] = 'Cookie'
            resp.headers['Referrer-Policy'] = 'no-referrer'
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            resp.headers['X-Frame-Options'] = 'DENY'
            resp.headers['Content-Security-Policy'] = " ".join([
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
            ])
            # Tag responses so the client/network tab can verify the refactor server
            resp.headers['X-OMAR-Server'] = 'OMAR_refactor'
            # Set/update CSRF cookie
            tok = flask_session.get('csrf_token')
            if tok:
                resp.set_cookie('csrf_token', tok, secure=app.config.get('SESSION_COOKIE_SECURE', False),
                                httponly=False, samesite=app.config.get('SESSION_COOKIE_SAMESITE','Strict'), path='/')
        except Exception:
            pass
        return resp

    # Minimal per-request colored trace so you can visually confirm the server in logs
    @app.before_request
    def _refactor_trace_before():
        try:
            if _USE_COLOR_BANNER and not request.path.startswith('/static'):
                print(f"{_CLR_MAGENTA}→ [OMAR_refactor] {request.method} {request.path}{_CLR_RESET}")
        except Exception:
            pass

    @app.after_request
    def _refactor_trace_after(resp):
        try:
            if _USE_COLOR_BANNER and not request.path.startswith('/static'):
                app.logger.info(f"{_CLR_CYAN}✓ [OMAR_refactor] {request.method} {request.path} {resp.status_code}{_CLR_RESET}")
        except Exception:
            pass
        return resp

    # Blueprints
    from .blueprints.general import bp as general_bp
    from .blueprints.patient import bp as patient_bp
    from .blueprints.patient_search import bp as patient_search_bp
    # Query API (optional if module not available)
    try:
        from .query.blueprints.query_api import bp as query_bp
    except Exception:
        query_bp = None
    # RAG API (optional if module not available)
    try:
        from .query.blueprints.rag_api import bp as rag_bp
    except Exception:
        rag_bp = None
    # Scribe API (optional until implemented)
    try:
        from .blueprints.scribe_api import bp as scribe_bp
    except Exception:
        scribe_bp = None
    # CPRS sync API (optional until implemented)
    try:
        from .blueprints.cprs_api import bp as cprs_bp
    except Exception:
        cprs_bp = None

    app.register_blueprint(general_bp)
    # Legacy-compatible endpoints at root for existing frontend JS (patient search/default list)
    app.register_blueprint(patient_search_bp)
    app.register_blueprint(patient_bp, url_prefix='/api/patient')
    if query_bp is not None:
        app.register_blueprint(query_bp, url_prefix='/api/query')
    if rag_bp is not None:
        app.register_blueprint(rag_bp, url_prefix='/api/rag')
    if scribe_bp is not None:
        app.register_blueprint(scribe_bp, url_prefix='/api/scribe')
    if cprs_bp is not None:
        app.register_blueprint(cprs_bp, url_prefix='/api/cprs')

    return app
