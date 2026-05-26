import cv2
import numpy as np
import json

# Load square mapping
with open('sqdict.json', 'r') as f:
    sq_points = json.load(f)

# Convert to numpy
for k in sq_points:
    sq_points[k] = np.array(sq_points[k], dtype=np.int32)

# Draw grid
def draw_outlines(frame):
    for square, pts in sq_points.items():
        cv2.polylines(frame, [pts], True, (255,255,255), 1)
        x, y, w, h = cv2.boundingRect(pts)
        cv2.putText(frame, square, (x, y+15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (0,0,255), 1)

# 🔥 Overlap-based mapping
def find_square_by_overlap(contour, shape):
    contour_mask = np.zeros(shape, dtype=np.uint8)
    cv2.drawContours(contour_mask, [contour], -1, 255, -1)

    best_square = None
    max_overlap = 0

    for sq, pts in sq_points.items():
        square_mask = np.zeros(shape, dtype=np.uint8)
        cv2.fillPoly(square_mask, [pts], 255)

        overlap = cv2.countNonZero(cv2.bitwise_and(contour_mask, square_mask))

        if overlap > max_overlap:
            max_overlap = overlap
            best_square = sq

    return best_square

cap = cv2.VideoCapture(1)

initial = None

print("Press 'r' twice to detect move | 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()
    draw_outlines(display)

    cv2.imshow("Chess CV", display)

    key = cv2.waitKey(1) & 0xFF

    # Capture initial frame
    if key == ord('r') and initial is None:
        initial = frame.copy()
        print("Captured initial frame")

    # Capture final frame
    elif key == ord('r') and initial is not None:
        final = frame.copy()
        print("Captured final frame")

        # --- PREPROCESS ---
        gray1 = cv2.cvtColor(initial, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY)

        # CLAHE for contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray1 = clahe.apply(gray1)
        gray2 = clahe.apply(gray2)

        # Edge detection
        edges1 = cv2.Canny(gray1, 50, 150)
        edges2 = cv2.Canny(gray2, 50, 150)

        # Differences
        diff_gray = cv2.absdiff(gray1, gray2)
        diff_edges = cv2.absdiff(edges1, edges2)

        # Combine
        diff = cv2.addWeighted(diff_gray, 0.6, diff_edges, 0.4, 0)

        # Threshold
        _, diff = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        # Morphology cleanup
        kernel = np.ones((5,5), np.uint8)
        diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, kernel)
        diff = cv2.dilate(diff, kernel, iterations=2)

        cv2.imshow("Difference", diff)

        # --- CONTOURS ---
        contours, _ = cv2.findContours(diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        detected = []

        for c in contours[:2]:
            if cv2.contourArea(c) < 800:
                continue

            square = find_square_by_overlap(c, gray1.shape)

            if square:
                detected.append((square, c))

            # Draw contour
            cv2.drawContours(display, [c], -1, (0,255,0), 2)

        # --- START / END DETECTION ---
        if len(detected) == 2:
            (sq1, c1), (sq2, c2) = detected

            # Create masks
            mask1 = np.zeros(gray1.shape, dtype=np.uint8)
            mask2 = np.zeros(gray1.shape, dtype=np.uint8)

            cv2.fillPoly(mask1, [sq_points[sq1]], 255)
            cv2.fillPoly(mask2, [sq_points[sq2]], 255)

            # Measure intensity change
            diff1 = cv2.mean(diff, mask=mask1)[0]
            diff2 = cv2.mean(diff, mask=mask2)[0]

            if diff1 > diff2:
                end = sq1
                start = sq2
            else:
                end = sq2
                start = sq1

            print(f"\n🔥 Move detected: {start} → {end}\n")

        else:
            print("❌ Move detection failed")

        cv2.imshow("Debug", display)

        # Reset
        initial = None

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()