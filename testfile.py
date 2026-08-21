from ultralytics import YOLO
import cv2

# Load the model
model = YOLO("yolov8s.pt") 

# Define input and output paths
image_path = "computer_lab.jpg"
output_path = "computer_lab_annotated.jpg"

# Run inference
results = model.predict(source=image_path, conf=0.25, classes=[0], imgsz=640)

# Extract count and save the image
for result in results:
    person_count = len(result.boxes)
    print(f"Total people detected: {person_count}")


# To save the image processed image out to file, uncomment below
#    # Generate the image array with bounding boxes drawn on it
#    annotated_frame = result.plot()
#    
#    # Save the array as a JPEG file
#    cv2.imwrite(output_path, annotated_frame)
#    print(f"Saved annotated image to: {output_path}")
