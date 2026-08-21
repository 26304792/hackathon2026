import getpass
import urllib.request
import json
import time
import socket

def silent_heartbeat():
    student_id = getpass.getuser() #e.g. 26304792
    backend_url = "https://slicer-coauthor-ferment.ngrok-free.dev/api/heartbeat"
    machine_id = socket.gethostname() #e.g. ITS-DBV-PC44
    payload = {"student_id": student_id, "machine_id": machine_id}
    json_data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(backend_url, data=json_data, method="POST")
    req.add_header('Content-Type', 'application/json')

    req.add_header('ngrok-skip-browser-warning', '1')   

    while True:
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
            
        time.sleep(3)

if __name__ == "__main__":
    silent_heartbeat()
