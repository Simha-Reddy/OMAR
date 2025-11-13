import os
import sys
from pathlib import Path

from waitress import serve

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if not os.getenv('OMAR_RUNTIME_ROOT'):
    os.environ['OMAR_RUNTIME_ROOT'] = str(ROOT_DIR / 'runtime')

if not os.getenv('OMAR_ENV_FILE'):
    env_path = ROOT_DIR / 'portable' / '.env'
    if env_path.is_file():
        os.environ['OMAR_ENV_FILE'] = str(env_path)

from omar import create_app

app = create_app()

if __name__ == '__main__':
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5050'))
    # Simple startup message so it doesn't look like it's "hanging"
    print(f"OMAR_refactor server starting on http://{host}:{port} (waitress) ...")
    print("Press Ctrl+C to stop.")
    serve(app, host=host, port=port, threads=4)
