import cv2 
from insightface.app import FaceAnalysis
import numpy as np

# Detection face model right here
app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=-1, det_size=(640,640))

#Benos ref image------------------------------
reference_image = cv2.imread("known_faces/benedict.jpeg")

if reference_image is None:
    print("Could not load Benedict's image")
    exit()

#detect my face
reference_faces = app.get(reference_image)

if len(reference_faces) == 0:
    print("No face found in Benedict's image")
    exit()

#Face embedding for Beno

benedict_embedding = reference_faces[0].embedding
#------------------------------------------------

#Load classes image --------------------------
image = cv2.imread("computer_lab.jpg")

if image is None:
    print("Could not load classroom image")
    exit()

faces = app.get(image)

print(f"Faces detected: {len(faces)}")
#------------------------------------------------

#Compare every face------------------------------
for face in faces:

    face_embedding = face.embedding

    similarity = np.dot(
        benedict_embedding,
        face_embedding
    ) / (
        np.linalg.norm(benedict_embedding)
        * np.linalg.norm(face_embedding)
    )

    x1, y1, x2, y2 = face.bbox.astype(int)

    print(f"Similarity: {similarity:.3f}")

    if similarity > 0.5:
        name = "BENEDICT"
    else:
        name = "UNKNOWN"

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    cv2.putText(
        image,
        name,
        (x1, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )
#------------------------------------------------------------
#Save result ------------------------------------------------
cv2.imwrite("faces_recognise.jpg", image)

print("Saved result to faces_recognised.jpg")