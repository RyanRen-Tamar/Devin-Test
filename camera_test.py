import cv2

def test_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access webcam")
        return False
    
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame from webcam")
        return False
    
    cap.release()
    print("Success: Camera is working properly")
    return True

if __name__ == "__main__":
    test_camera()
