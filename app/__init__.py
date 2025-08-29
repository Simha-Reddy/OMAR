import os
import shutil
from flask import Flask
from flask_session import Session
from dotenv import load_dotenv
from .extensions import init_openai, init_vista

REQUIRED_DIRS = [
    "chunks",
    "transcripts",
    "temp_pdf",
    os.path.join("templates", "default"),
    os.path.join("templates", "custom"),
    os.path.join("templates", "patient_instructions"),
    "modules"
]

def create_app():
    load_dotenv()
    # Compute project root (one level up from this file's directory)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..'))
    templates_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')

    # Explicitly point Flask to the top-level templates/ and static/ folders
    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-flask-key")

    # Feature flags
    app.config['SAFE_MODULES_ENABLED'] = os.getenv("SAFE_MODULES_ENABLED", "0").strip().lower() in ("1", "true", "yes")

    # Session config
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_session")
    app.config["SESSION_PERMANENT"] = False

    # Optionally clear server-side session cache on startup
    # Enabled by default; set CLEAR_SESSIONS_ON_START=0 to keep previous sessions
    clear_on_start = os.getenv("CLEAR_SESSIONS_ON_START", "1").strip().lower() in ("1", "true", "yes")
    if clear_on_start:
        sess_dir = app.config["SESSION_FILE_DIR"]
        try:
            if os.path.isdir(sess_dir):
                shutil.rmtree(sess_dir, ignore_errors=True)
        except Exception:
            # Non-fatal; continue even if cleanup fails
            pass
        # Ensure directory exists after cleanup
        os.makedirs(sess_dir, exist_ok=True)

    Session(app)

    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)

    # Initialize external clients
    init_openai(app)
    init_vista(app)  # socket client (best-effort)

    # Store deploy names
    app.config['DEPLOY_CHAT'] = os.getenv("AZURE_DEPLOYMENT_NAME")
    app.config['DEPLOY_EMBED'] = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", app.config['DEPLOY_CHAT'])

    # Register blueprints
    from .blueprints.scribe import bp as scribe_bp
    from .blueprints.explore import bp as explore_bp
    from .blueprints.modules import bp as modules_bp
    from .blueprints.general import bp as general_bp
    from .blueprints.patient import bp as patient_bp  # re-added
    from .blueprints.agent_api import bp as agent_api_bp
    from .blueprints.fhir import bp as fhir_bp

    app.register_blueprint(general_bp)
    app.register_blueprint(scribe_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(patient_bp)  # re-added
    app.register_blueprint(agent_api_bp)
    app.register_blueprint(fhir_bp)

    return app
