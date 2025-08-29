from flask import Blueprint, request, jsonify, session
import os, json
import numpy as np
from flask import current_app
from smart_problems_azureembeddings import hybrid_search  # passed to runner
from module_runner import run_module_by_name

bp = Blueprint('modules', __name__, url_prefix='/modules')

MODULES_DIR = 'modules'

@bp.route('', methods=['GET'])
def list_root_modules():
    files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.txt')] if os.path.isdir(MODULES_DIR) else []
    return jsonify(files)

@bp.route('/all', methods=['GET'])
def get_modules_full():
    if not os.path.isdir(MODULES_DIR):
        return jsonify({'error': 'Modules folder not found'}), 404
    modules = []
    for filename in os.listdir(MODULES_DIR):
        if filename.endswith('.txt'):
            with open(os.path.join(MODULES_DIR, filename), 'r', encoding='utf-8') as f:
                modules.append({'filename': filename, 'content': f.read()})
    return jsonify(modules)

@bp.route('/load/<name>')
def load_module(name):
    path = os.path.join(MODULES_DIR, name)
    if not os.path.isfile(path):
        return 'Not found', 404
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

@bp.route('/save', methods=['POST'])
def save_module():
    data = request.get_json()
    name = data.get('name')
    content = data.get('content')
    if not name or not content:
        return 'Missing name or content', 400
    os.makedirs(MODULES_DIR, exist_ok=True)
    with open(os.path.join(MODULES_DIR, name), 'w', encoding='utf-8') as f:
        f.write(content)
    return 'OK'

@bp.route('/delete/<name>', methods=['DELETE'])
def delete_module(name):
    path = os.path.join(MODULES_DIR, name)
    if os.path.isfile(path):
        os.remove(path)
        return 'OK'
    return 'Not found', 404

@bp.route('/run', methods=['POST'])
def run_module():
    data = request.get_json()
    module_name = data.get('module')
    chunks = session.get('explore_chunks', [])
    vectors = np.array(session.get('explore_vectors', []))
    inverted_index = {k: set(v) for k, v in session.get('explore_index', {}).items()}
    client = current_app.config.get('OPENAI_CLIENT')
    deploy_chat = current_app.config.get('DEPLOY_CHAT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')
    result = run_module_by_name(
        module_name, data, chunks, vectors, inverted_index, client, deploy_chat, deploy_embed, hybrid_search
    )
    return jsonify(result)
