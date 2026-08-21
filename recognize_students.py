import cv2
import sqlite3
import numpy as np
from insightface.app import FaceAnalysis

# LOAD FACE MODEL
# -------------------------

app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=-1, det_size=(640, 640))

# LOAD STUDENTS FROM DATABASE
# -------------------------

connection = sqlite3.connect("students.db")
cursor = connection.cursor()

cursor.execute("SELECT id, name, embedding FROM students")
students = cursor.fetchall()

connection.close()

print(f"Students in database: {len(students)}")

# Convert database embeddings back into NumPy arrays
known_students = []

for student in students:
    student_id, name, embedding_blob = student

    embedding = np.frombuffer(
        embedding_blob,
        dtype=np.float32
    )

    known_students.append(
        (student_id, name, embedding)
    )

# LOAD CLASSROOM IMAGE
# -------------------------

image = cv2.imread("computer_lab.jpg")

if image is None:
    print("Could not load classroom image")
    exit()

# Detect faces
faces = app.get(image)

print(f"Faces detected: {len(faces)}")

# RECOGNIZE EACH FACE
# -------------------------

for face in faces:

    face_embedding = face.embedding

    best_name = "UNKNOWN"
    best_similarity = -1

    # Compare against every enrolled student
    for student_id, name, known_embedding in known_students:

        similarity = np.dot(
            known_embedding,
            face_embedding
        ) / (
            np.linalg.norm(known_embedding)
            * np.linalg.norm(face_embedding)
        )

        if similarity > best_similarity:
            best_similarity = similarity
            best_name = name

    # Only accept the match if similarity is high enough
    if best_similarity < 0.5:
        best_name = "UNKNOWN"

    print(
        f"Best match: {best_name} "
        f"(similarity: {best_similarity:.3f})"
    )

    # Bounding box
    x1, y1, x2, y2 = face.bbox.astype(int)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    # Name
    cv2.putText(
        image,
        best_name,
        (x1, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

# SAVE RESULT
# -------------------------

cv2.imwrite("students_recognised.jpg", image)

print("Saved result to students_recognised.jpg")