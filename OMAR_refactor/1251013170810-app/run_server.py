import os
from waitress import serve
from app import create_app

app = create_app()

if __name__ == '__main__':
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5050'))
    # Simple startup message so it doesn't look like it's "hanging"
    print(f"OMAR_refactor server starting on http://{host}:{port} (waitress) ...")
    print("Press Ctrl+C to stop.")
    serve(app, host=host, port=port, threads=4)
