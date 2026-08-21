import cv2
import sqlite3
import numpy as np
from pathlib import Path
from insightface.app import FaceAnalysis


# -------------------------
# LOAD INSIGHTFACE
# -------------------------

app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=-1, det_size=(640, 640))


# -------------------------
# CONNECT TO DATABASE
# -------------------------

connection = sqlite3.connect("face_database.db")
cursor = connection.cursor()


# -------------------------
# CREATE TABLE
# -------------------------

cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        embedding BLOB NOT NULL
    )
""")


# -------------------------
# PROCESS KNOWN FACES
# -------------------------

known_faces_folder = Path("known_faces")

for image_path in known_faces_folder.glob("*.jpeg"):

    # Filename becomes student ID
    student_id = image_path.stem

    print(f"Processing {student_id}...")

    # Load image
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Could not load {image_path}")
        continue

    # Detect faces
    faces = app.get(image)

    if len(faces) == 0:
        print(f"No face found for {student_id}")
        continue

    if len(faces) > 1:
        print(f"Multiple faces found for {student_id}")
        continue

    # Get face embedding
    embedding = faces[0].embedding

    # Convert NumPy float32 array into bytes
    embedding_blob = embedding.astype(np.float32).tobytes()

    # Store in database
    cursor.execute(
        """
        INSERT OR REPLACE INTO students (student_id, embedding)
        VALUES (?, ?)
        """,
        (student_id, embedding_blob)
    )

    print(f"Added {student_id}")


# -------------------------
# SAVE DATABASE
# -------------------------

connection.commit()
connection.close()

print("\nDatabase built successfully!")