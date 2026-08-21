import cv2
import sqlite3
import numpy as np
from insightface.app import FaceAnalysis

# Load InsightFace
app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=-1, det_size=(640, 640))

# Get student information
name = input("Student name: ")
image_path = input("Image path: ")

# Load image
image = cv2.imread(image_path)

if image is None:
    print("Could not load image.")
    exit()

# Detect faces
faces = app.get(image)

if len(faces) == 0:
    print("No face detected.")
    exit()

if len(faces) > 1:
    print("Multiple faces detected. Please use an image containing one student.")
    exit()

# Get embedding
embedding = faces[0].embedding

# Convert embedding to SQLite-compatible bytes
embedding_blob = embedding.astype(np.float32).tobytes()

# Connect to database
connection = sqlite3.connect("students.db")
cursor = connection.cursor()

# Save student
cursor.execute(
    "INSERT INTO students (name, embedding) VALUES (?, ?)",
    (name, embedding_blob)
)

connection.commit()
connection.close()

print(f"{name} enrolled successfully!")