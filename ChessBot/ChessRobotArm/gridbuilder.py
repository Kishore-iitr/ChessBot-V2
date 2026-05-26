import cv2
import json

cap = cv2.VideoCapture(1)

mapping = {}
current_points = []
square_index = 0

files = ['a','b','c','d','e','f','g','h']
ranks = ['8','7','6','5','4','3','2','1']

square_list = [f + r for r in ranks for f in files]

def click(event, x, y, flags, param):
    global current_points, square_index

    if event == cv2.EVENT_LBUTTONDOWN and square_index < 64:
        current_points.append([x, y])
        print(f"{square_list[square_index]} - Point {len(current_points)}: ({x},{y})")

        # Once 4 points are clicked → save square
        if len(current_points) == 4:
            sq = square_list[square_index]
            mapping[sq] = current_points.copy()

            print(f"Saved {sq}")
            current_points.clear()
            square_index += 1

print("Click 4 corners per square (consistent order!)")
print("Recommended: TL → TR → BR → BL")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()

    # Show current square + point number
    if square_index < 64:
        text = f"{square_list[square_index]} | Point {len(current_points)+1}/4"
    else:
        text = "DONE! Press 's' to save"

    cv2.putText(display, text, (20,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0,255,0), 2)

    # Draw current points (red)
    for p in current_points:
        cv2.circle(display, tuple(p), 5, (0,0,255), -1)

    # Draw completed squares (blue)
    for sq, pts in mapping.items():
        for p in pts:
            cv2.circle(display, tuple(p), 3, (255,0,0), -1)

    cv2.imshow("Corner Mapping", display)
    cv2.setMouseCallback("Corner Mapping", click)

    key = cv2.waitKey(1) & 0xFF

    # Save JSON
    if key == ord('s'):
        with open("sqdict.json", "w") as f:
            json.dump(mapping, f, indent=2)
        print("Saved sqdict.json")

    # Undo last square
    if key == ord('u') and square_index > 0:
        square_index -= 1
        last_sq = square_list[square_index]
        mapping.pop(last_sq, None)
        current_points.clear()
        print(f"Removed {last_sq}")

    # Reset everything
    if key == ord('r'):
        mapping.clear()
        current_points.clear()
        square_index = 0
        print("Reset all")

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()