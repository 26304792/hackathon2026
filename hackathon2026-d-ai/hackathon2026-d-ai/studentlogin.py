import getpass
import json
import os
import socket
import ssl
import time
import urllib.request

DEFAULT_BACKEND_URL = "https://127.0.0.1:5000/api/heartbeat"


def silent_heartbeat():
    student_id = getpass.getuser()  # e.g. 26304792
    backend_url = os.environ.get("ATTENDANCE_BACKEND_URL", DEFAULT_BACKEND_URL)
    machine_id = socket.gethostname()  # e.g. ITS-DBV-PC44
    payload = {"student_id": student_id, "machine_id": machine_id}
    json_data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(backend_url, data=json_data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("ngrok-skip-browser-warning", "1")

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    while True:
        try:
            urllib.request.urlopen(req, timeout=5, context=ssl_context)
        except Exception:
            pass

        time.sleep(3)


if __name__ == "__main__":
    silent_heartbeat()
