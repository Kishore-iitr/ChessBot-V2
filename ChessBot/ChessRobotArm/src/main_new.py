#Play a full game using Computer Vision with JSON-based servo control

import cv2
import numpy as np
import json
import chess
import chess.svg
from cairosvg import svg2png
import chess.engine
import serial
import random
from time import sleep

engine = chess.engine.SimpleEngine.popen_uci(r"stockfish\stockfish-windows-2022-x86-64-avx2.exe")

# Load square dictionary for CV-based move detection
with open('sqdict.json', 'r') as fp:
    sq_points = json.load(fp)

# Load servo angles mapping (will be added later)
# Expected format: {"E7": [servo1_angle, servo2_angle, gripper_state], ...}
try:
    with open('servo_angles.json', 'r') as fp:
        raw_servo_mapping = json.load(fp)
        # Normalize keys so both 'e2' and 'E2' work.
        servo_mapping = {str(k).upper(): v for k, v in raw_servo_mapping.items()}
except FileNotFoundError:
    print("Warning: servo_angles.json not found. Please add the JSON file with grid-to-servo mappings.")
    servo_mapping = {}

# Initialize serial connection to Arduino
try:
    ser = serial.Serial('COM4', 9600)
    print("Connected to Arduino on COM4")
except:
    print("Warningimmg: Could not connect to Arduino on COM4")
    ser = None

DISCARD_KEYS = ("DISCARD", "BIN", "TRASH")
DEFAULT_DISCARD_POSE = [50, 94, 0]

#Returns the square given a point within the square
def find_square(x: float, y: float): 
    for square in sq_points:
        points = np.array(sq_points[square], np.int32)
        if cv2.pointPolygonTest(points, (x, y), False) > 0:
            return square
    return None

#Outline the squares
def draw_outlines(sq_points: dict, frame, show_text = False) -> None:
    for square in sq_points:
        points = sq_points[square]
        points = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [points], True, (255, 255, 255), thickness=1)
        x, y, w, h = cv2.boundingRect(points)
        if show_text:
            cv2.putText(frame, square, (x, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

#Show board using python-chess SVGRendering
def show_board(board: chess.Board, size=900, move = None) -> None:
    if move is not None:
        sq1, sq2 = chess.parse_square(move[:2]), chess.parse_square(move[2:4])
        svgwrap = chess.svg.board(board, size=size, fill=dict.fromkeys([sq1, sq2], '#ced264'))
    else:
        svgwrap = chess.svg.board(board, size=size)
    svg2png(svgwrap, write_to='output.png')
    cv2.imshow('Game', cv2.imread('output.png'))

# Send command to Arduino
def send_command_to_arduino(command_value) -> None:
    """Send a serial command string or numeric payload to Arduino."""
    if ser is not None:
        try:
            ser.write(bytes(f"{command_value}\n", 'utf-8'))
            sleep(0.05)
            print(f"Sent command: {command_value}")
        except:
            print(f"Error sending command: {command_value}")

# Wait for Arduino acknowledgement
def wait_for_arduino_done() -> None:
    """Wait for Arduino to send 'done' message"""
    if ser is not None:
        try:
            while True:
                if ser.in_waiting:
                    rec = ser.readline().decode().strip()
                    print(f"Arduino: {rec}")
                    if "done" in rec.lower():
                        break
        except:
            print("Error reading from Arduino")

def get_pose_for_square(square: str):
    """Return [servo1, servo2, servo3] for a square key present in servo mapping."""
    key = square.upper()
    if key not in servo_mapping:
        return None
    return servo_mapping[key]

def get_discard_pose():
    """Return a configured discard/bin pose from JSON or fallback defaults."""
    for key in DISCARD_KEYS:
        if key in servo_mapping:
            return servo_mapping[key]
    return DEFAULT_DISCARD_POSE

def go_to_pose(servo1_angle: int, servo2_angle: int, servo3_angle: int) -> None:
    """Move the arm to a 3-servo pose and wait for completion."""
    send_command_to_arduino(int(servo1_angle))
    wait_for_arduino_done()
    send_command_to_arduino(int(servo2_angle) + 200)
    wait_for_arduino_done()
    send_command_to_arduino(int(servo3_angle) + 400)
    wait_for_arduino_done()

def set_gripper(open_gripper: bool) -> None:
    """Open or close gripper and wait for completion."""
    send_command_to_arduino(192 if open_gripper else 191)
    wait_for_arduino_done()

def pick_from_square(square: str) -> bool:
    """Go to square and pick the piece."""
    pose = get_pose_for_square(square)
    if pose is None or len(pose) < 3:
        print(f"Warning: Square {square.upper()} not found in servo mapping")
        return False
    # Ensure gripper is open before approaching pickup square.
    set_gripper(True)
    go_to_pose(pose[0], pose[1], pose[2])
    # Close gripper at the initial square to pick the piece.
    set_gripper(False)
    send_command_to_arduino(190)
    wait_for_arduino_done()
    return True

def drop_to_square(square: str) -> bool:
    """Go to square and drop the currently held piece."""
    pose = get_pose_for_square(square)
    if pose is None or len(pose) < 3:
        print(f"Warning: Square {square.upper()} not found in servo mapping")
        return False
    go_to_pose(pose[0], pose[1], pose[2])
    set_gripper(True)
    send_command_to_arduino(190)
    wait_for_arduino_done()
    return True

def drop_to_discard() -> None:
    """Drop a held piece to configured discard/bin location."""
    discard_pose = get_discard_pose()
    if discard_pose is None or len(discard_pose) < 3:
        print("Warning: DISCARD pose missing or incomplete in servo mapping")
        return
    go_to_pose(discard_pose[0], discard_pose[1], discard_pose[2])
    set_gripper(True)
    send_command_to_arduino(190)
    wait_for_arduino_done()

# Execute move using servo angles from JSON
def execute_move_with_servo(sq1: str, sq2: str, is_capture: bool = False, capture_square: str = None) -> bool:
    """
    Execute a chess move using servo angles from the JSON mapping
    
    Args:
        sq1: Starting square (e.g., 'E7')
        sq2: Ending square (e.g., 'G6')
        is_capture: Whether the move is a capture
        capture_square: Square of captured piece (for en-passant support)

    Returns:
        True if the complete physical move succeeded, else False.
    """
    sq1_upper = sq1.upper()
    sq2_upper = sq2.upper()
    
    # Check if move squares exist in servo mapping
    if sq1_upper not in servo_mapping or sq2_upper not in servo_mapping:
        print(f"Warning: Square {sq1_upper} or {sq2_upper} not found in servo mapping")
        return False
    
    try:
        # Get servo angles for starting and ending squares
        sq1_data = servo_mapping[sq1_upper]
        servo1_angle = sq1_data[0]
        servo2_angle = sq1_data[1]
        servo3_angle = sq1_data[2]
        
        # Get servo angles for ending square
        sq2_data = servo_mapping[sq2_upper]
        servo1_final = sq2_data[0]
        servo2_final = sq2_data[1]
        servo3_final = sq2_data[2]
        
        print(f"Moving from {sq1_upper} to {sq2_upper}")
        print(f"Start angles: Servo1={servo1_angle}, Servo2={servo2_angle}, Servo3={servo3_angle}")
        print(f"End angles: Servo1={servo1_final}, Servo2={servo2_final}, Servo3={servo3_final}")
        
        # Capture sequence: remove opponent piece first, then play our move.
        if is_capture:
            target_square = (capture_square if capture_square is not None else sq2).upper()
            print(f"Capture detected at {target_square}. Removing captured piece first.")
            if pick_from_square(target_square):
                drop_to_discard()
            else:
                print("Capture removal failed. Aborting move to avoid collision.")
                return False

        # Normal move sequence: open+close at initial square, then drop at final square.
        set_gripper(True)
        go_to_pose(servo1_angle, servo2_angle, servo3_angle)
        set_gripper(False)
        send_command_to_arduino(190)
        wait_for_arduino_done()

        go_to_pose(servo1_final, servo2_final, servo3_final)
        set_gripper(True)
        send_command_to_arduino(190)
        wait_for_arduino_done()
        
        print(f"Move completed: {sq1_upper} to {sq2_upper}")
        return True
        
    except Exception as e:
        print(f"Error executing move: {e}")
        return False

# Initialize video capture
cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

initial = []
final = []
bounding_boxes = []
centers = []
highlights = set()

board = chess.Board()
comp_move = True
human_capture_enabled = False
show_board(board)
cv2.waitKey(2)

print("Chess game started. Press 'r' to record human moves, 'q' to quit")

while not board.is_game_over():
    ret, frame = cap.read()
    if not ret:
        print("Error reading frame from camera")
        break
        
    draw_outlines(sq_points, frame)
    cv2.imshow('Frame', frame)

    # Computer's turn
    if comp_move:
        # Block manual capture while robot is executing its move.
        human_capture_enabled = False
        initial = []
        final = []

        result = engine.play(board, chess.engine.Limit(time=random.random()))
        comp_move_uci = result.move.uci()
        (sq1, sq2) = (comp_move_uci[:2], comp_move_uci[2:4])

        print(f"\nComputer plays: {comp_move_uci}")
        
        # Check for special moves
        is_capture = board.is_capture(result.move)

        capture_square = sq2
        if board.is_en_passant(result.move):
            direction = -8 if board.turn == chess.WHITE else 8
            capture_square = chess.square_name(result.move.to_square + direction)
        
        move_command = f"MOVE {comp_move_uci}"
        if is_capture:
            move_command += f" CAPTURE {capture_square}"
        send_command_to_arduino(move_command)
        wait_for_arduino_done()
        
        # Update board state
        board.push(result.move)
        show_board(board, move=comp_move_uci)
        comp_move = False
        human_capture_enabled = True
        
        # Resume image capture for human move
        print("Waiting for human move. Press 'r' to record move...")

    # Record human move from video
    if human_capture_enabled and (cv2.waitKey(1) & 0xFF == ord('r')):
        if len(initial) == 0:
            initial = frame.copy()
            print("Recording initial position...")
        elif len(final) == 0:
            print('Move captured - processing...')
            final = frame.copy()

            # Get the absolute difference between the initial and final frames
            gray1 = cv2.cvtColor(initial, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray1, gray2)
            _, diff = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

            # Remove noise from the difference frame
            diff = cv2.dilate(diff, None, iterations=4)
            kernel_size = 3
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
            diff = cv2.erode(diff, kernel, iterations=6)
            
            # Find relevant contours
            contours, _ = cv2.findContours(diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            sorted_contours_and_areas = sorted(zip(contours, [cv2.contourArea(c) for c in contours]), key=lambda x: x[1], reverse=True)
            try:
                contours = [sorted_contours_and_areas[0][0], sorted_contours_and_areas[1][0]]
                cv2.drawContours(frame, contours, 1, (255, 0, 0), 4)

                # Find the bounding boxes of the contours
                bounding_boxes = [cv2.boundingRect(c) for c in contours]

                # Find the center point of the bounding boxes 
                centers = [(x + w//2, y + 0.7*h) for (x, y, w, h) in bounding_boxes]
                highlights = set()
                for p in centers:
                    highlights.add(find_square(*p))
                initial = []
                final = []
            except:
                highlights = set()
                highlights.add('rand')
                highlights.add('placeholder')
                initial = []
                final = []
            
            # Process detected move
            if len(highlights) == 2:
                try:
                    sq1, sq2 = highlights.pop(), highlights.pop()
                    # Determine correct order based on whose turn it is
                    if board.color_at(chess.parse_square(sq1)) == board.turn:
                        start, end = sq1, sq2
                    else:
                        start, end = sq2, sq1
                    uci = start + end
                    board.push_uci(uci)
                    print(f"Human plays: {uci}")
                except Exception as e:
                    uci = input(f"Couldn't record proper move. Error: {e}. Override: ")
                    board.push_uci(uci)
                    print(f"Move accepted: {uci}")
                
                show_board(board, move=uci)
                highlights = set()
                centers = []
                comp_move = True
                human_capture_enabled = False

    # Exit command
    if cv2.waitKey(2) & 0xFF == ord('q'):
        print("Exiting game...")
        break

    cv2.imshow('Frame', frame)

# Cleanup
show_board(board)
cap.release()
cv2.destroyAllWindows()
if ser is not None:
    ser.close()
print("Game over. Final board state displayed.")
