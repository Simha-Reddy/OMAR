from flask import Blueprint, render_template, request, jsonify
import os
from pathlib import Path

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

# --- Prompt endpoints (read from static/prompts) ---

def _root_dir():
    # OMAR_refactor root dir
    return Path(__file__).resolve().parents[2]

def _static_prompts_dir():
    return _root_dir() / 'static' / 'prompts'

@bp.route('/get_prompts')
def get_prompts():
    """Aggregate note scribe prompt templates from static/prompts/note_scribe_prompts.
    Returns a name->text mapping for use in the Note module.
    """
    base = _static_prompts_dir() / 'note_scribe_prompts'
    out = {}
    try:
        if base.exists():
            # Walk subfolders (e.g., default/, custom/, site/)
            for p in base.rglob('*'):
                if p.is_file() and p.suffix.lower() in ('.txt', '.md'):
                    name = p.stem
                    try:
                        text = p.read_text(encoding='utf-8', errors='ignore')
                    except Exception:
                        text = ''
                    if text:
                        # If duplicate names exist, prefer non-default directories over default
                        rel = p.relative_to(base)
                        parts = rel.parts
                        is_default = len(parts) > 1 and parts[0].lower() == 'default'
                        if name in out and is_default:
                            # Keep existing non-default/custom
                            continue
                        out[name] = text
    except Exception:
        pass
    return jsonify(out)

@bp.route('/load_patient_instructions_prompt')
def load_patient_instructions_prompt():
    """Load patient instructions/AVS prompt.
    Prefers custom override under static/prompts/patient_instructions/custom/patient_instructions.txt,
    else falls back to static/prompts/patient_instructions/default/default_instructions.txt.
    """
    base = _static_prompts_dir() / 'patient_instructions'
    candidates = [
        base / 'custom' / 'patient_instructions.txt',
        base / 'default' / 'default_instructions.txt',
    ]
    for p in candidates:
        try:
            if p.exists():
                return p.read_text(encoding='utf-8'), 200
        except Exception:
            continue
    return '', 404

@bp.route('/save_patient_instructions_prompt', methods=['POST'])
def save_patient_instructions_prompt():
    data = request.get_json(silent=True) or {}
    text = str(data.get('text') or '')
    try:
        target_dir = _static_prompts_dir() / 'patient_instructions' / 'custom'
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / 'patient_instructions.txt'
        target.write_text(text, encoding='utf-8')
        return jsonify({'status': 'saved'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/default_patient_instructions_prompt')
def default_patient_instructions_prompt():
    p = _static_prompts_dir() / 'patient_instructions' / 'default' / 'default_instructions.txt'
    try:
        if p.exists():
            return p.read_text(encoding='utf-8'), 200
    except Exception:
        pass
    return '', 404

@bp.route('/load_health_summary_prompt')
def load_health_summary_prompt():
    p = _static_prompts_dir() / 'health_summary_prompt.txt'
    try:
        if p.exists():
            return p.read_text(encoding='utf-8'), 200
    except Exception:
        pass
    return '', 404

@bp.route('/load_one_liner_prompt')
def load_one_liner_prompt():
    p = _static_prompts_dir() / 'one_liner.txt'
    try:
        if p.exists():
            return p.read_text(encoding='utf-8'), 200
    except Exception:
        pass
    return '', 404
