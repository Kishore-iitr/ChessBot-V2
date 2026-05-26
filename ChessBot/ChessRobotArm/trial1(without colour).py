import cv2
import numpy as np
import json
import time
import os

# Load square mapping
sqdict_path = os.path.join(os.path.dirname(__file__), 'sqdict.json')
with open(sqdict_path, 'r') as f:
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

# 🔥 Method 3: find square using overlap
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

def log(msg):
    print(f"[trial1] {msg}", flush=True)

selected_points = []
roi_polygon = None

def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(selected_points) < 4:
        selected_points.append((x, y))
        log(f"Selected point {len(selected_points)}: ({x}, {y})")


def draw_selected_roi(frame):
    if len(selected_points) > 0:
        for p in selected_points:
            cv2.circle(frame, p, 4, (0, 255, 255), -1)
    if len(selected_points) == 4:
        pts = np.array(selected_points, dtype=np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 255), 2)


def draw_status_text(frame, text):
    if not text:
        return
    cv2.rectangle(frame, (8, 8), (420, 42), (0, 0, 0), -1)
    cv2.putText(frame, text, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def build_roi_mask(shape):
    mask = np.zeros(shape, dtype=np.uint8)
    if roi_polygon is not None:
        cv2.fillPoly(mask, [roi_polygon], 255)
    return mask


initial = None
final_move_text = None

log("Camera script started")
log(f"Loaded square mapping from: {sqdict_path}")
log("Select 4 board corner points with mouse, then press 'c' to confirm")
log("Press 'x' to reset selected points | 'q' to quit")

cv2.namedWindow("Chess CV")
cv2.setMouseCallback("Chess CV", on_mouse)

while roi_polygon is None:
    ret, frame = cap.read()
    if not ret:
        log("Failed to read frame while selecting ROI.")
        cap.release()
        cv2.destroyAllWindows()
        raise SystemExit(1)

    selection_view = frame.copy()
    draw_selected_roi(selection_view)
    cv2.putText(selection_view, "Click 4 corners, press 'c' to confirm", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.imshow("Chess CV", selection_view)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('x'):
        selected_points.clear()
        log("ROI points reset")
    elif key == ord('c'):
        if len(selected_points) == 4:
            roi_polygon = np.array(selected_points, dtype=np.int32)
            log(f"ROI confirmed with points: {selected_points}")
        else:
            log("Please select exactly 4 points before confirming")
    elif key == ord('q'):
        log("Quit requested during ROI selection")
        cap.release()
        cv2.destroyAllWindows()
        raise SystemExit(0)

log("Press 'r' to capture initial frame | 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        log("Failed to read frame from camera. Exiting loop.")
        break

    display = frame.copy()
    draw_outlines(display)
    draw_selected_roi(display)
    draw_status_text(display, f"Final move: {final_move_text}" if final_move_text else "Awaiting move...")
    cv2.imshow("Chess CV", display)

    key = cv2.waitKey(1) & 0xFF

    # Capture initial
    if key == ord('r') and initial is None:
        initial = frame.copy()
        log("Captured initial frame. Monitoring for move every 1s...")


        last_move = None
        attempt = 0
        wait_before_capture = 0.5
        while True:
            attempt += 1
            # First comparison happens at 0.5s, retries happen every 1s
            time.sleep(wait_before_capture)
            ret2, final = cap.read()
            if not ret2:
                log("Camera error while reading comparison frame.")
                break

            log(f"Comparison attempt #{attempt}: captured frame")

            display2 = final.copy()
            draw_outlines(display2)
            draw_selected_roi(display2)

            gray1 = cv2.cvtColor(initial, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY)

            diff = cv2.absdiff(gray1, gray2)
            _, diff_bin = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

            # Clean noise
            kernel = np.ones((5,5), np.uint8)
            diff_bin = cv2.morphologyEx(diff_bin, cv2.MORPH_OPEN, kernel)
            diff_bin = cv2.dilate(diff_bin, kernel, iterations=2)

            # Restrict processing to selected board ROI
            roi_mask = build_roi_mask(gray1.shape)
            diff_bin = cv2.bitwise_and(diff_bin, roi_mask)

            cv2.imshow("Difference", diff_bin)

            # Find contours
            contours, _ = cv2.findContours(diff_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            log(f"Found {len(contours)} contours (before filtering)")

            changed_pixels = cv2.countNonZero(diff_bin)
            log(f"Changed pixels: {changed_pixels}")

            if changed_pixels < 500:
                log("No move/change detected. Capturing next frame after 1 second...")
                cv2.imshow("Debug", display2)
                wait_before_capture = 1.0
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    log("Quit requested during monitoring.")
                    initial = None
                    break
                continue

            detected_squares = []

            for c in contours[:2]:
                if cv2.contourArea(c) < 500:
                    continue
                square = find_square_by_overlap(c, gray1.shape)
                if square:
                    detected_squares.append((square, c))
                cv2.drawContours(display2, [c], -1, (0,255,0), 2)

            log(f"Detected square candidates: {[sq for (sq, _) in detected_squares]}")

            # --- DETERMINE START & END ---
            move_detected = False
            move_str = None
            if len(detected_squares) == 2:
                (sq1, c1), (sq2, c2) = detected_squares

                # Create masks
                mask1 = np.zeros(gray1.shape, dtype=np.uint8)
                mask2 = np.zeros(gray1.shape, dtype=np.uint8)

                cv2.fillPoly(mask1, [sq_points[sq1]], 255)
                cv2.fillPoly(mask2, [sq_points[sq2]], 255)

                # Measure intensity change
                diff1 = cv2.mean(diff_bin, mask=mask1)[0]
                diff2 = cv2.mean(diff_bin, mask=mask2)[0]

                if diff1 > diff2:
                    end = sq1
                    start = sq2
                else:
                    end = sq2
                    start = sq1

                move_str = f"{start}->{end}"
                log(f"Move detected: {move_str}")
                cv2.imshow("Debug", display2)
                move_detected = True
            else:
                log("Move detection failed. Retrying...")
                cv2.imshow("Debug", display2)
                wait_before_capture = 1.0

            # Allow user to quit during monitoring
            if cv2.waitKey(1) & 0xFF == ord('q'):
                log("Quit requested during monitoring.")
                initial = None
                break

            # If a move is detected, require confirmation in next frame
            if move_detected:
                # Wait 1 second and capture again
                time.sleep(1)
                ret3, confirm_frame = cap.read()
                if not ret3:
                    log("Camera error while reading confirmation frame.")
                    initial = None
                    break

                log(f"Captured confirmation frame for move {move_str}")

                display3 = confirm_frame.copy()
                draw_outlines(display3)
                draw_selected_roi(display3)
                draw_status_text(display3, f"Confirming: {move_str}")

                gray3 = cv2.cvtColor(confirm_frame, cv2.COLOR_BGR2GRAY)
                diff_confirm = cv2.absdiff(gray1, gray3)
                _, diff_bin_confirm = cv2.threshold(diff_confirm, 30, 255, cv2.THRESH_BINARY)
                diff_bin_confirm = cv2.morphologyEx(diff_bin_confirm, cv2.MORPH_OPEN, kernel)
                diff_bin_confirm = cv2.dilate(diff_bin_confirm, kernel, iterations=2)
                diff_bin_confirm = cv2.bitwise_and(diff_bin_confirm, roi_mask)

                contours_c, _ = cv2.findContours(diff_bin_confirm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours_c = sorted(contours_c, key=cv2.contourArea, reverse=True)

                detected_squares_c = []
                for c in contours_c[:2]:
                    if cv2.contourArea(c) < 500:
                        continue
                    square = find_square_by_overlap(c, gray1.shape)
                    if square:
                        detected_squares_c.append((square, c))
                    cv2.drawContours(display3, [c], -1, (0,255,0), 2)

                move_str_c = None
                if len(detected_squares_c) == 2:
                    (sq1c, c1c), (sq2c, c2c) = detected_squares_c
                    mask1c = np.zeros(gray1.shape, dtype=np.uint8)
                    mask2c = np.zeros(gray1.shape, dtype=np.uint8)
                    cv2.fillPoly(mask1c, [sq_points[sq1c]], 255)
                    cv2.fillPoly(mask2c, [sq_points[sq2c]], 255)
                    diff1c = cv2.mean(diff_bin_confirm, mask=mask1c)[0]
                    diff2c = cv2.mean(diff_bin_confirm, mask=mask2c)[0]
                    if diff1c > diff2c:
                        endc = sq1c
                        startc = sq2c
                    else:
                        endc = sq2c
                        startc = sq1c
                    move_str_c = f"{startc}->{endc}"
                    log(f"Confirmation move detected: {move_str_c}")
                    cv2.imshow("Debug", display3)
                else:
                    log("Confirmation frame did not produce two valid squares")

                if move_str_c == move_str:
                    final_move_text = move_str
                    draw_status_text(display3, f"Final move: {move_str}")
                    cv2.imshow("Chess CV", display3)
                    log(f"Move finalised: {move_str}")
                    initial = None
                    break
                else:
                    log("Move not confirmed, keep checking...")
                    wait_before_capture = 1.0
                    # Continue monitoring

    elif key == ord('q'):
        log("Quit requested from main loop.")
        break

cap.release()
cv2.destroyAllWindows()
log("Camera script exited cleanly")