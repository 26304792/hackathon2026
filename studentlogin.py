import getpass
import urllib.request
import json
import time

def silent_heartbeat():
    student_id = getpass.getuser()
    #https://slicer-coauthor-ferment.ngrok-free.dev/
    backend_url = "https://slicer-coauthor-ferment.ngrok-free.dev/api/heartbeat"
    
    payload = {"student_id": student_id, "location": "ITS"}
    json_data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(backend_url, data=json_data, method="POST")
    req.add_header('Content-Type', 'application/json')

    req.add_header('ngrok-skip-browser-warning', '1')   

    # The infinite loop keeps the script running in the background
    while True:
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            # Silently ignore errors so the student isn't bothered
            pass
            
        time.sleep(3)

if __name__ == "__main__":
    silent_heartbeat()
