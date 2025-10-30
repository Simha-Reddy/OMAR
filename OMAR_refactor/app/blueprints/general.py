from flask import Blueprint, render_template

bp = Blueprint('general', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/note')
def note_tab():
    return render_template('tabs/note.html', title='Note (Scribe)')
