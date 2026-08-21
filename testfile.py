from ultralytics import YOLO
import cv2

# 1. Load the YOLOv8 model. 
# We use 'yolov8s.pt' (small) instead of 'n' (nano) for better accuracy on partial bodies.
model = YOLO("yolov8s.pt") 

# 2. Define the path to your photo
image_path = "computer_lab.jpg"

# 3. Run inference
#   - conf=0.25: Lowering confidence helps catch occluded (head/shoulder) people.
#   - classes=[0]: COCO dataset class 0 is 'person'.
#   - imgsz=640: Standard image size. Increase to 1280 if the image is wide and heads are tiny.
#   - save=True: Automatically saves a copy of the image with bounding boxes drawn.
results = model.predict(source=image_path, conf=0.25, classes=[0], imgsz=640, save=True)

# 4. Extract and print the count
for result in results:
    # result.boxes contains the bounding boxes for all detected people
    person_count = len(result.boxes)
    print(f"Total people detected: {person_count}")
    
    # Optional: Display the result immediately using OpenCV
    annotated_frame = result.plot()
    cv2.imshow("YOLOv8 Detection", annotated_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
