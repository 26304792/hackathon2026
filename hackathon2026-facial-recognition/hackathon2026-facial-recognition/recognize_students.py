import cv2
import os
import sqlite3
import numpy as np
import requests
import urllib3
from insightface.app import FaceAnalysis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ATTENDANCE_SERVER_URL = os.environ.get(
    "ATTENDANCE_SERVER_URL", "https://127.0.0.1:5000"
)
ATTENDANCE_CLASSROOM = os.environ.get("ATTENDANCE_CLASSROOM", "AG-ITS")


def confirm_attendance(student_ids):
    if not student_ids:
        return

    url = f"{ATTENDANCE_SERVER_URL.rstrip('/')}/api/facial_confirm"
    payload = {
        "student_ids": student_ids,
        "classroom": ATTENDANCE_CLASSROOM,
    }

    try:
        response = requests.post(url, json=payload, timeout=10, verify=False)
        result = response.json()
        print(f"Attendance server response: {result}")
    except requests.RequestException as exc:
        print(f"Could not reach attendance server: {exc}")


# -------------------------
# LOAD FACE MODEL
# -------------------------

app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=-1, det_size=(640, 640))


# -------------------------
# LOAD STUDENTS FROM DATABASE
# -------------------------

connection = sqlite3.connect("face_database.db")
cursor = connection.cursor()

cursor.execute(
    "SELECT id, student_id, embedding FROM students"
)

students = cursor.fetchall()

connection.close()

print(f"Students in database: {len(students)}")


# -------------------------
# CONVERT DATABASE EMBEDDINGS
# -------------------------

known_students = []

for student in students:

    database_id, student_id, embedding_blob = student

    embedding = np.frombuffer(
        embedding_blob,
        dtype=np.float32
    )

    known_students.append(
        (database_id, student_id, embedding)
    )


# -------------------------
# LOAD CLASSROOM IMAGE
# -------------------------

image = cv2.imread("computer_lab.jpg")

if image is None:
    print("Could not load classroom image")
    exit()


# -------------------------
# DETECT FACES
# -------------------------

faces = app.get(image)

print(f"Faces detected: {len(faces)}")


# -------------------------
# RECOGNIZE EACH FACE
# -------------------------

recognized_student_ids = []

for face in faces:

    face_embedding = face.embedding

    best_student_id = "UNKNOWN"
    best_similarity = -1

    # Compare against every student
    for database_id, student_id, known_embedding in known_students:

        similarity = np.dot(
            known_embedding,
            face_embedding
        ) / (
            np.linalg.norm(known_embedding)
            * np.linalg.norm(face_embedding)
        )

        if similarity > best_similarity:
            best_similarity = similarity
            best_student_id = student_id


    # Recognition threshold
    if best_similarity < 0.5:
        best_student_id = "UNKNOWN"


    print(
        f"Best match: {best_student_id} "
        f"(similarity: {best_similarity:.3f})"
    )

    if best_student_id != "UNKNOWN":
        recognized_student_ids.append(best_student_id)


    # -------------------------
    # DRAW BOUNDING BOX
    # -------------------------

    x1, y1, x2, y2 = face.bbox.astype(int)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )


    # -------------------------
    # DISPLAY STUDENT ID
    # -------------------------

    cv2.putText(
        image,
        best_student_id,
        (x1, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )


# -------------------------
# SAVE RESULT
# -------------------------

cv2.imwrite(
    "students_recognised.jpg",
    image
)

print("Saved result to students_recognised.jpg")

confirm_attendance(recognized_student_ids)