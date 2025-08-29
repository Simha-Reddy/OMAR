from flask import Blueprint, render_template, request, jsonify, session
import os, uuid
from datetime import datetime
from ..utils import get_resource_path
from record_audio import start_recording_thread, stop_recording
from flask import current_app
from ..utils import expand_patient_dotphrases

bp = Blueprint('scribe', __name__, url_prefix='/scribe')

@bp.route('/')
def scribe_home():
    default_dir = os.path.join('templates', 'default')
    custom_dir = os.path.join('templates', 'custom')
    default_templates = []
    custom_templates = []
    if os.path.exists(default_dir):
        default_templates = [os.path.splitext(f)[0] for f in os.listdir(default_dir) if f.endswith(('.txt', '.md'))]
    if os.path.exists(custom_dir):
        custom_templates = [os.path.splitext(f)[0] for f in os.listdir(custom_dir) if f.endswith(('.txt', '.md'))]
    return render_template('scribe.html', default_templates=default_templates, custom_templates=custom_templates, safe_modules_enabled=current_app.config.get('SAFE_MODULES_ENABLED', False))

# Recording state kept in app config
def _is_recording():
    return current_app.config.setdefault('IS_RECORDING', False)

def _set_recording(val: bool):
    current_app.config['IS_RECORDING'] = val

@bp.route('/recording_status')
def recording_status():
    return jsonify({'is_recording': _is_recording()})

@bp.route('/start_recording', methods=['POST'])
def start_recording_route():
    if not _is_recording():
        start_recording_thread()
        _set_recording(True)
    return 'Recording started', 200

@bp.route('/stop_recording', methods=['POST'])
def stop_recording_route():
    if _is_recording():
        stop_recording()
        _set_recording(False)
    return 'Recording stopped', 200

@bp.route('/live_transcript')
def live_transcript():
    try:
        with open(get_resource_path('live_transcript.txt'), 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except FileNotFoundError:
        return '', 200

@bp.route('/set_live_transcript', methods=['POST'])
def set_live_transcript():
    data = request.get_json()
    text = data.get('text', '')
    try:
        with open(get_resource_path('live_transcript.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        return jsonify({'status': 'set'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clear_live_transcript', methods=['POST'])
def clear_live_transcript():
    try:
        with open(get_resource_path('live_transcript.txt'), 'w', encoding='utf-8') as f:
            f.write('')
        return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/status')
def scribe_status():
    chunk_dir = 'chunks'
    wavs = [f for f in os.listdir(chunk_dir) if f.endswith('.wav')] if os.path.isdir(chunk_dir) else []
    txts = [f for f in os.listdir(chunk_dir) if f.endswith('.txt')] if os.path.isdir(chunk_dir) else []
    txt_basenames = {os.path.splitext(f)[0] for f in txts}
    pending = [f for f in wavs if os.path.splitext(f)[0] not in txt_basenames]
    transcript_path = get_resource_path('live_transcript.txt')
    try:
        with open(transcript_path, 'r') as f:
            transcript = f.read()
    except FileNotFoundError:
        transcript = ''
    return jsonify({'pending_chunks': len(pending), 'transcript': transcript, 'is_recording': _is_recording()})

@bp.route('/create_note', methods=['POST'])
def create_note():
    data = request.get_json()
    transcript = data.get('transcript', '')
    visit_notes = data.get('visit_notes', '')
    prompt_text = data.get('prompt_text', '').strip()
    prompt_type = data.get('prompt_type', '')
    if not prompt_text:
        prompt_clean = prompt_type.replace('(Custom)', '').strip()
        base_default = os.path.join('templates', 'default', prompt_clean)
        base_custom = os.path.join('templates', 'custom', prompt_clean)
        for ext in ['.txt', '.md']:
            if os.path.exists(base_default + ext):
                with open(base_default + ext, 'r', encoding='utf-8') as f:
                    prompt_text = f.read(); break
            if os.path.exists(base_custom + ext):
                with open(base_custom + ext, 'r', encoding='utf-8') as f:
                    prompt_text = f.read(); break
    if not prompt_text:
        return jsonify({'note': f"Prompt template for '{prompt_type}' not found."}), 404
    # Expand dot-phrases in the prompt and inputs for better context
    try:
        prompt_text = expand_patient_dotphrases(prompt_text, for_query=True)
        transcript = expand_patient_dotphrases(transcript, for_query=True)
        visit_notes = expand_patient_dotphrases(visit_notes, for_query=True)
    except Exception:
        pass
    messages = [
        {'role': 'system', 'content': 'You are a helpful clinical documentation assistant.'},
        {'role': 'user', 'content': prompt_text + '\n\nNOTES DURING VISIT:\n' + visit_notes.strip() + '\n\nTRANSCRIPT:\n' + transcript.strip()}
    ]
    client = current_app.config.get('OPENAI_CLIENT')
    model = 'gpt-4o'
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.5)
        note = resp.choices[0].message.content.strip()
        # Post-process AI output for any [[...]] expansions
        try:
            note = expand_patient_dotphrases(note)
        except Exception:
            pass
        return jsonify({'note': note, 'messages': messages})
    except Exception as e:
        return jsonify({'note': f'Error generating note: {e}'}), 500

@bp.route('/chat_feedback', methods=['POST'])
def chat_feedback():
    data = request.get_json()
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'reply': 'No conversation context provided.'}), 400
    # Expand any dot-phrases present in user messages before sending
    try:
        for m in messages:
            if isinstance(m, dict) and isinstance(m.get('content'), str):
                m['content'] = expand_patient_dotphrases(m['content'], for_query=True)
    except Exception:
        pass
    client = current_app.config.get('OPENAI_CLIENT')
    try:
        resp = client.chat.completions.create(model='gpt-4o', messages=messages, temperature=0.5)
        reply = resp.choices[0].message.content.strip()
        # Expand any [[...]] in assistant reply
        try:
            reply = expand_patient_dotphrases(reply)
        except Exception:
            pass
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f'Error: {e}'}), 500
