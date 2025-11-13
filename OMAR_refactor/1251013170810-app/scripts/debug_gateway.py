import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.gateways.vista_socket_gateway import VistaSocketGateway

gw = VistaSocketGateway(host="vista.puget-sound.med.va.gov", port=19212, access="sr3355", verify="L@scruce2025!", default_context="OR CPRS GUI CHART")
try:
    gw.connect()
    client = gw._client
    print("connected context", client.context)
    lock = client._lock
    lock.acquire()
    try:
        raw = client._invoke_locked("ORQPT DEFAULT PATIENT LIST", [])
        print("raw length", len(raw))
        print("raw snippet", repr(raw[:200]))
    finally:
        lock.release()
finally:
    gw.close()
