from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_from_directory, session
import os, json, glob, time, re
from datetime import datetime, timedelta
from ..utils import get_resource_path
from ..utils import get_dotphrase_commands
from ..extensions import login_vista_with_credentials
from flask import current_app
from record_audio import stop_recording  # Added to allow stopping recording on exit
import threading  # <-- added for delayed hard-exit

bp = Blueprint('general', __name__)

@bp.route('/')
def index():
    return render_template('landing.html')

@bp.route('/login', methods=['POST'])
def login_route():
    try:
        data = request.get_json(silent=True) or {}
        site = (data.get('site') or 'puget-sound').strip().lower()
        access = (data.get('access') or '').strip()
        verify = (data.get('verify') or '').strip()
        if not access or not verify:
            return jsonify({'error': 'Missing access and/or verify code'}), 400
        info = login_vista_with_credentials(current_app, site, access, verify)
        return jsonify({'status': 'ok', 'site': site, 'host': info.get('host'), 'port': info.get('port')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/settings')
def settings():
    prompt_files = os.listdir(get_resource_path('templates/custom')) if os.path.exists(get_resource_path('templates/custom')) else []
    return render_template('settings.html', prompt_templates=prompt_files)

@bp.route('/archive')
def archive():
    transcripts = []
    transcript_dir = 'transcripts'
    if os.path.exists(transcript_dir):
        files = sorted(os.listdir(transcript_dir), reverse=True)
        for f in files:
            path = os.path.join(transcript_dir, f)
            if not f.endswith('.json'):
                continue
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            try:
                base = os.path.splitext(f)[0]
                ts = base.replace('session_', '')
                dt = datetime.strptime(ts, '%Y%m%d_%H%M')
                readable_time = dt.strftime('%B %d, %Y at %I:%M %p')
            except Exception:
                readable_time = f
            transcripts.append({'filename': f, 'display_time': readable_time, 'content': content})
    return render_template('archive.html', transcripts=transcripts)

@bp.route('/delete_transcripts', methods=['POST'])
def delete_transcripts():
    filenames = request.form.getlist('filenames')
    for fname in filenames:
        path = os.path.join('transcripts', fname)
        if os.path.exists(path):
            os.remove(path)
    return redirect('/archive')

@bp.route('/load_patient_instructions_prompt')
def load_patient_instructions_prompt():
    path = os.path.join('templates', 'patient_instructions', 'patient_instructions.txt')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return '', 404

@bp.route('/load_health_summary_prompt')
def load_health_summary_prompt():
    path = os.path.join('templates', 'health_summary_prompt.txt')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read(), 200
    return '', 404

@bp.route('/save_patient_instructions_prompt', methods=['POST'])
def save_patient_instructions_prompt():
    data = request.get_json()
    text = data.get('text', '')
    os.makedirs(os.path.join('templates', 'patient_instructions'), exist_ok=True)
    path = os.path.join('templates', 'patient_instructions', 'patient_instructions.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return jsonify({'status': 'saved'})

@bp.route('/default_patient_instructions_prompt')
def default_patient_instructions_prompt():
    path = os.path.join('templates', 'patient_instructions', 'default_instructions.txt')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read(), 200
    return '', 404

@bp.route('/save_template', methods=['POST'])
def save_template():
    data = request.get_json()
    name = data.get('name')
    text = data.get('text')
    if name and text:
        os.makedirs(get_resource_path('templates/custom'), exist_ok=True)
        if not name.endswith(('.txt', '.md')):
            name += '.txt'
        with open(os.path.join(get_resource_path('templates/custom'), name), 'w', encoding='utf-8') as f:
            f.write(text)
        return redirect(url_for('general.settings'))
    return 'Invalid data', 400

@bp.route('/load_template/<name>')
def load_template(name):
    base = os.path.join('templates', 'custom', name)
    for ext in ['.txt', '.md']:
        path = base + ext
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    return '', 404

@bp.route('/list_custom_templates')
def list_custom_templates():
    folder = os.path.join('templates', 'custom')
    if not os.path.exists(folder):
        return jsonify([])
    files = [os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith(('.txt', '.md'))]
    return jsonify(files)

@bp.route('/templates/custom/<filename>')
def serve_custom_template(filename):
    return send_from_directory('templates/custom', filename)

@bp.route('/delete_template/<name>', methods=['DELETE'])
def delete_template(name):
    base = os.path.join('templates', 'custom', name)
    for ext in ['.txt', '.md']:
        path = base + ext
        if os.path.exists(path):
            os.remove(path)
            return 'Deleted', 200
    return 'Not found', 404

@bp.route('/get_prompts')
def get_prompts():
    prompts = {}
    for folder in [get_resource_path('templates/default'), get_resource_path('templates/custom')]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(('.txt', '.md')):
                    with open(os.path.join(folder, file), 'r', encoding='utf-8', errors='ignore') as f:
                        name = os.path.splitext(file)[0]
                        prompts[name] = f.read()
    return jsonify(prompts)

@bp.route('/render_markdown', methods=['POST'])
def render_markdown():
    data = request.get_json()
    md_text = data.get('markdown', '')
    try:
        import markdown
        html = markdown.markdown(md_text, extensions=['extra', 'sane_lists'])
        return jsonify({'html': html})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'})
    file = request.files['pdf']
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'})
    try:
        if not os.path.exists('temp_pdf'):
            os.makedirs('temp_pdf')
        temp_path = os.path.join('temp_pdf', file.filename)
        file.save(temp_path)
        markdown_text = convert_pdf_to_markdown(temp_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'text': markdown_text})
    except Exception as e:
        return jsonify({'error': f'PDF processing error: {e}'})

def convert_pdf_to_markdown(pdf_path):
    import pdfplumber, re
    markdown_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            markdown_text.append(f"\n## Page {page.page_number}\n")
            tables = page.extract_tables()
            for table in tables:
                markdown_text.append("\n| " + " | ".join(str(cell) if cell is not None else '' for cell in table[0]) + " |\n")
                markdown_text.append("|" + "|".join(['---'] * len(table[0])) + "|\n")
                for row in table[1:]:
                    markdown_text.append("| " + " | ".join(str(cell) if cell is not None else '' for cell in row) + " |\n")
                markdown_text.append("\n")
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                if line.isupper() or re.match(r'^(HPI|ASSESSMENT|PLAN|LABS?|RADIOLOGY|MEDICATIONS?)[:\s-]*$', line.strip(), re.I):
                    markdown_text.append(f"\n### {line.strip()}\n")
                else:
                    markdown_text.append(line + "\n")
    return "".join(markdown_text)

@bp.route('/save_full_session', methods=['POST'])
def save_full_session():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'No session name provided'}), 400
    # Sanitize filename for Windows
    safe = re.sub(r'[<>:"/\\|?*]+', '_', str(name)).strip()
    safe = safe.replace('..', '_')
    if not safe:
        safe = f"session-{int(time.time())}"
    # Prefer posted scribe/explore if present, else fall back to server session
    scribe_payload = data.get('scribe', session.get('scribe', {}))
    explore_payload = data.get('explore', session.get('explore', {}))
    patient_meta = session.get('patient_meta', {}) or {}
    os.makedirs('transcripts', exist_ok=True)
    filepath = os.path.join('transcripts', f"{safe}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({'scribe': scribe_payload, 'explore': explore_payload, 'patient_meta': patient_meta}, f)
    return jsonify({'status': 'Session saved to disk', 'filename': f"{safe}.json"}), 200

@bp.route('/save_session', methods=['POST'])
def save_session_route():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    session['scribe'] = data.get('scribe', {})
    session['explore'] = data.get('explore', {})
    return jsonify({'status': 'Session saved'}), 200

@bp.route('/load_session', methods=['GET'])
def load_session_route():
    return jsonify({
        'scribe': session.get('scribe', {}),
        'explore': session.get('explore', {}),
        'patient_record': session.get('patient_record', {})
    }), 200

@bp.route('/clear_session', methods=['POST'])
def clear_session_route():
    session.pop('scribe', None)
    session.pop('explore', None)
    return jsonify({'status': 'Session cleared'}), 200

@bp.route('/load_saved_session/<filename>')
def load_saved_session(filename):
    filepath = os.path.join('transcripts', filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    session['scribe'] = data.get('scribe', {})
    session['explore'] = data.get('explore', {})
    return jsonify({'status': 'Session loaded', 'data': data}), 200

@bp.route('/list_sessions')
def list_sessions():
    transcript_dir = 'transcripts'
    if not os.path.exists(transcript_dir):
        return jsonify([])
    files = [f for f in os.listdir(transcript_dir) if f.endswith('.json')]
    return jsonify(files)

@bp.route('/transcripts/<filename>')
def get_transcript(filename):
    path = os.path.join('transcripts', filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/json'}

@bp.route('/delete_session/<filename>', methods=['DELETE'])
def delete_session(filename):
    path = os.path.join('transcripts', filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Not found'}), 404

@bp.route('/delete_old_sessions', methods=['POST', 'GET'])
def delete_old_sessions():
    """Delete transcript JSON files older than N days (default 10).
    Accepts query/body param 'days'. Returns list of deleted filenames.
    """
    try:
        days_param = None
        if request.method == 'GET':
            days_param = request.args.get('days')
        else:
            payload = request.get_json(silent=True) or {}
            days_param = payload.get('days')
        days = int(days_param) if days_param is not None else 10
    except Exception:
        days = 10
    cutoff = time.time() - (days * 86400)
    transcript_dir = 'transcripts'
    if not os.path.isdir(transcript_dir):
        return jsonify({'deleted': [], 'kept': 0, 'days': days})
    deleted = []
    kept = 0
    for f in os.listdir(transcript_dir):
        if not f.endswith('.json'):
            continue
        p = os.path.join(transcript_dir, f)
        try:
            mtime = os.path.getmtime(p)
            if mtime < cutoff:
                os.remove(p)
                deleted.append(f)
            else:
                kept += 1
        except Exception:
            # If stat fails, skip file
            kept += 1
            continue
    return jsonify({'deleted': deleted, 'kept': kept, 'days': days})

@bp.route('/transcription_complete')
def transcription_complete():
    completed_jsons = [f for f in os.listdir('chunks') if f.endswith('_final.wav.json')] if os.path.isdir('chunks') else []
    return jsonify({'done': len(completed_jsons) > 0})

@bp.route('/shutdown', methods=['POST'])
def shutdown():
    from flask import request
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func:
        shutdown_func()
    return 'Server shutting down...'

@bp.route('/session_data')
def session_data():
    return jsonify(dict(session))

@bp.route('/end_session', methods=['POST'])
def end_session():
    now = datetime.now()
    # Build default like "8-27-25 at 1025 with <name>"
    patient_name = (session.get('patient_meta') or {}).get('name') or ''
    display = f"{now.month}-{now.day}-{str(now.year)[2:]} at {now.strftime('%H%M')} with {patient_name}"
    # Sanitize filename
    safe = re.sub(r'[<>:"/\\|?*]+', '_', display).strip()
    safe = safe.replace('..', '_')
    os.makedirs('transcripts', exist_ok=True)
    filepath = os.path.join('transcripts', f"{safe}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({'scribe': session.get('scribe', {}), 'explore': session.get('explore', {}), 'patient_meta': session.get('patient_meta', {})}, f)
    session.pop('scribe', None)
    session.pop('explore', None)
    return jsonify({'status': 'Session ended', 'filename': f"{safe}.json"})

@bp.route('/dotphrase_commands', methods=['GET'])
def dotphrase_commands():
    try:
        return jsonify({'commands': get_dotphrase_commands()})
    except Exception as e:
        return jsonify({'commands': [], 'error': str(e)}), 500

@bp.route('/exit_page', methods=['GET'])
def serve_exit_page():
    # Lightweight route to render the exit page after client calls /exit
    return render_template('exit.html')

# --- New: Exit route to fully clear session/patient state and stop recording ---
@bp.route('/exit', methods=['POST'])
def exit_app():
    try:
        # Stop any active recording if flagged
        if current_app.config.get('IS_RECORDING'):
            try:
                stop_recording()
            except Exception:
                pass
            current_app.config['IS_RECORDING'] = False

        # Close any active VistA socket client
        try:
            vista_client = current_app.config.get('VISTA_CLIENT')
            if vista_client:
                try:
                    vista_client.close()
                except Exception:
                    pass
                current_app.config['VISTA_CLIENT'] = None
        except Exception:
            pass

        # Terminate background monitor process if tracked
        try:
            proc = current_app.config.get('MONITOR_PROC')
            if proc and getattr(proc, 'poll', None) and proc.poll() is None:
                try:
                    proc.terminate()
                    # give a moment then kill if still alive
                    import time as _t
                    _t.sleep(0.2)
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
                current_app.config['MONITOR_PROC'] = None
        except Exception:
            pass

        # Clear all server-side session data (scribe/explore/patient etc.)
        session.clear()

        # Clear live transcript on disk
        try:
            with open(get_resource_path('live_transcript.txt'), 'w', encoding='utf-8') as f:
                f.write('')
        except Exception:
            pass

        # Gracefully ask Werkzeug dev server to shut down, then hard-exit the process shortly after
        try:
            shutdown_func = request.environ.get('werkzeug.server.shutdown')
            if shutdown_func:
                shutdown_func()
        except Exception:
            pass
        # Ensure the entire program exits (tray, background threads, etc.)
        try:
            threading.Timer(0.5, lambda: os._exit(0)).start()
        except Exception:
            pass

        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500
