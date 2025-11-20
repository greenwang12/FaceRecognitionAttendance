import cv2
import insightface
import numpy as np
import requests
import json
import mediapipe as mp

BACKEND_URL = "http://127.0.0.1:8000/api/v1/students/register-face"

# Face detector
mp_face = mp.solutions.face_detection.FaceDetection(model_selection=1,
                                                    min_detection_confidence=0.6)

# InsightFace model
fa = insightface.app.FaceAnalysis(name="buffalo_l")
fa.prepare(ctx_id=-1)

cam = cv2.VideoCapture(0)
print("[INFO] Enrollment camera started. Press SPACE to capture.")

student_id = input("Enter student_id to enroll: ")

while True:
    ret, frame = cam.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = mp_face.process(rgb)

    if result.detections:
        cv2.putText(frame, "Face Detected - Press SPACE to Enroll",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0), 2)

    cv2.imshow("Enrollment", frame)
    key = cv2.waitKey(1)

    if key == 32:  # SPACE
        if not result.detections:
            print("[ERR] No face detected. Try again.")
            continue

        # Insightface face embedding
        faces = fa.get(rgb)
        if len(faces) == 0:
            print("[ERR] No face embeddings. Try again.")
            continue

        embedding = faces[0].embedding.tolist()

        payload = {
            "student_id": int(student_id),
            "embedding": embedding
        }

        r = requests.post(BACKEND_URL, json=payload)
        print("[API RESPONSE]", r.json())

        break

    if key == 27:  # ESC
        break

cam.release()
cv2.destroyAllWindows()
