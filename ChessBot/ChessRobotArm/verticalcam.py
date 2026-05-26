import cv2
import numpy as np

cap = cv2.VideoCapture(1)

initial = None

print("Press 'r' twice to detect move | 'q' to quit")

# Convert (row, col) → chess notation
def get_square(x, y, w, h):
    cell_w = w // 8
    cell_h = h // 8

    col = x // cell_w
    row = y // cell_h

    files = ['a','b','c','d','e','f','g','h']
    ranks = ['8','7','6','5','4','3','2','1']

    return files[int(col)] + ranks[int(row)]

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape

    # Draw grid
    for i in range(1, 8):
        cv2.line(frame, (0, i*h//8), (w, i*h//8), (255,255,255), 1)
        cv2.line(frame, (i*w//8, 0), (i*w//8, h), (255,255,255), 1)

    cv2.imshow("Top View Chess", frame)

    key = cv2.waitKey(1) & 0xFF

    # Capture initial
    if key == ord('r') and initial is None:
        initial = frame.copy()
        print("Captured initial")

    # Capture final
    elif key == ord('r') and initial is not None:
        final = frame.copy()
        print("Captured final")

        gray1 = cv2.cvtColor(initial, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(gray1, gray2)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        thresh = cv2.dilate(thresh, None, iterations=2)
        thresh = cv2.erode(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        squares = []

        for c in contours[:2]:
            if cv2.contourArea(c) < 500:
                continue

            x, y, wc, hc = cv2.boundingRect(c)
            cx = x + wc // 2
            cy = y + hc // 2

            square = get_square(cx, cy, w, h)
            squares.append(square)

            # draw center
            cv2.circle(frame, (cx, cy), 5, (0,0,255), -1)

        if len(squares) == 2:
            print(f"Move: {squares[0]} → {squares[1]}")
        else:
            print("Detection failed")

        initial = None

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()