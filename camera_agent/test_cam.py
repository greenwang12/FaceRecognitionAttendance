import cv2

cap = cv2.VideoCapture(0)

print("cap.isOpened():", cap.isOpened())

ret, frame = cap.read()
print("first read -> ret:", ret, "frame:", None if frame is None else frame.shape)

if not cap.isOpened():
    raise SystemExit("Camera could not be opened. Try index 1 or 2.")

print("Press q to quit.")
while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame read failed.")
        break
    cv2.imshow("TEST CAMERA", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
