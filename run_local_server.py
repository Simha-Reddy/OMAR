from app import create_app

import os, sys, glob, subprocess
import threading, time
import webbrowser
import requests


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def clean_old_session():
    if os.path.isdir('chunks'):
        for ext in ('*.wav', '*.txt', '*.json'):
            for file in glob.glob(os.path.join('chunks', ext)):
                try:
                    os.remove(file)
                except Exception:
                    pass
    try:
        with open(get_resource_path('live_transcript.txt'), 'w', encoding='utf-8') as f:
            f.write('')
    except Exception:
        pass


def start_monitor():
    script_name = 'monitor_transcription.py'
    if getattr(sys, 'frozen', False):
        script_path = os.path.join(os.path.dirname(sys.executable), 'monitor_transcription.exe')
        if os.path.exists(script_path):
            try:
                proc = subprocess.Popen([script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return proc
            except Exception:
                pass
    else:
        script_path = os.path.join(os.path.dirname(__file__), script_name)
    try:
        proc = subprocess.Popen([sys.executable, script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except Exception:
        return None


def wait_for_server(host='127.0.0.1', port=5000, timeout=20.0):
    url = f'http://{host}:{port}/'
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=0.75)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


app = create_app()

if __name__ == '__main__':
    clean_old_session()

    # Start background monitor and keep handle for cleanup (/exit already terminates it)
    monitor_proc = start_monitor()
    try:
        if monitor_proc:
            app.config['MONITOR_PROC'] = monitor_proc
    except Exception:
        pass

    # Start Flask in a background thread
    def run_server():
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait until server is ready
    wait_for_server('127.0.0.1', 5000, timeout=20.0)

    # Open default browser (Edge if it is the default)
    try:
        webbrowser.open_new('http://127.0.0.1:5000/')
    except Exception:
        pass

    # Keep the process alive until UI triggers /exit, which will os._exit(0)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # If interrupted, attempt a graceful shutdown
    try:
        requests.post('http://127.0.0.1:5000/exit', timeout=1.5)
    except Exception:
        pass

    time.sleep(0.5)
