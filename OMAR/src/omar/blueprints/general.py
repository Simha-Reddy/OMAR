from flask import Blueprint, jsonify, render_template

bp = Blueprint('general', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/note')
def note_tab():
    return render_template('tabs/note.html', title='Note (Scribe)')

# Workspace and simple pages
@bp.route('/workspace')
def workspace():
    # Enable width-based redirect to mobile and safe module mode by default
    return render_template('workspace.html', enable_width_detection=True, safe_modules_enabled=True)

@bp.route('/settings')
def settings():
    return render_template('settings.html')

@bp.route('/archive')
def archive():
    return render_template('archive.html')

@bp.route('/endpoints')
def endpoints():
    return render_template('endpoints.html')

@bp.route('/exit')
def exit_page():
    return render_template('exit.html')


@bp.route('/healthz')
def healthcheck():
    """Lightweight container health probe."""
    return jsonify({'status': 'ok'}), 200

