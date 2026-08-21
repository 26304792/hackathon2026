import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# 1. Enrolled student roster for Lab 204
ENROLLED_STUDENTS = ["26304792", "21987654", "20456789"]

# 2. In-memory dictionary to store active heartbeats: { student_id: timestamp }
active_heartbeats = {}

# Timeout threshold (if no ping in 10 seconds, student is marked offline)
TIMEOUT_SECONDS = 10


# ROUTE A: Received from the silent student script on login/heartbeat
@app.route("/api/heartbeat", methods=["POST"])
def receive_heartbeat():
  data = request.json
  student_id = data.get("student_id")

  if student_id:
    # Record or refresh the current Unix timestamp
    active_heartbeats[student_id] = time.time()
    return jsonify({"status": "success"}), 200

  return jsonify({"status": "error", "message": "Missing student_id"}), 400


# ROUTE B: Polled by the Godot/Flask Lecturer Dashboard every 2-3 seconds
@app.route("/api/active-students", methods=["GET"])
def get_active_students():
  current_time = time.time()
  online_students = []
  expired_students = []

  # Check every student currently in memory
  for student_id, last_seen in active_heartbeats.items():
    time_diff = current_time - last_seen

    if time_diff > TIMEOUT_SECONDS:
      # Mark student for cleanup if they timed out
      expired_students.append(student_id)
    else:
      # Determine if they are an intruder
      is_intruder = student_id not in ENROLLED_STUDENTS

      online_students.append({
          "student_id": student_id,
          "is_intruder": is_intruder,
          "seconds_since_ping": round(time_diff, 1),
      })

  # Remove offline students from dictionary to free up memory
  for student_id in expired_students:
    del active_heartbeats[student_id]

  return jsonify({
      "total_active": len(online_students),
      "students": online_students,
  })


if __name__ == "__main__":
  app.run(port=5000, debug=True)
