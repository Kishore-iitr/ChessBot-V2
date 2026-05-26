import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

try:
    import serial
except Exception:
    serial = None

try:
    import pygame
except Exception:
    pygame = None


WINDOW_NAME = "Servo Mapper"
DEFAULT_OUTPUT = "servo_angles.json"
ARDUINO_HEADER = Path(__file__).resolve().parent / "arduino" / "controller" / "servo_angles_data.h"

# Windows OpenCV arrow key codes from waitKeyEx
KEY_LEFT = 2424832
KEY_UP = 2490368
KEY_RIGHT = 2555904
KEY_DOWN = 2621440


def clamp(value: int, lower: int = 0, upper: int = 180) -> int:
    return max(lower, min(upper, value))


def load_sq_points(path: Path) -> dict:
    with open(path, "r") as fp:
        return json.load(fp)


def find_square(x: float, y: float, sq_points: dict):
    for square in sq_points:
        points = np.array(sq_points[square], np.int32)
        if cv2.pointPolygonTest(points, (x, y), False) > 0:
            return square.upper()
    return None


def draw_outlines(sq_points: dict, frame, show_text: bool = True) -> None:
    for square in sq_points:
        points = np.array(sq_points[square], dtype=np.int32)
        cv2.polylines(frame, [points], True, (255, 255, 255), thickness=1)
        if show_text:
            x, y, _, _ = cv2.boundingRect(points)
            cv2.putText(frame, square.upper(), (x, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 255), 1)


def write_arduino_header(mapping: dict, header_path: Path) -> None:
    """Generate a C++ header containing the square-to-servo pose table."""
    entries = []
    for square, pose in sorted(mapping.items()):
        if not isinstance(pose, (list, tuple)) or len(pose) < 3:
            continue
        square_upper = str(square).upper()
        try:
            s1, s2, s3 = int(pose[0]), int(pose[1]), int(pose[2])
        except Exception:
            continue
        entries.append(f'  {{"{square_upper}", {s1}, {s2}, {s3}}}')

    if entries:
        pose_rows = ",\n".join(entries)
        count_line = f"static const size_t SQUARE_POSES_COUNT = {len(entries)};"
    else:
        pose_rows = '  {"__EMPTY__", 0, 0, 0}'
        count_line = "static const size_t SQUARE_POSES_COUNT = 0;"

    header_text = "\n".join([
        "#pragma once",
        "",
        "#include <Arduino.h>",
        "",
        "struct SquarePose {",
        "  const char* square;",
        "  uint8_t servo1;",
        "  uint8_t servo2;",
        "  uint8_t servo3;",
        "};",
        "",
        "static const SquarePose SQUARE_POSES[] = {",
        pose_rows,
        "};",
        "",
        count_line,
        "",
    ])
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(header_text, encoding="utf-8")


class ArduinoBridge:
    def __init__(self, port: str, baud: int):
        self.ser = None
        self.ack_timeout_s = 1.8
        if serial is None:
            print("pyserial not installed, running without Arduino output")
            return
        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
            print(f"Connected to Arduino on {port} @ {baud}")
            time.sleep(1.0)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception as exc:
            print(f"Could not connect to Arduino: {exc}")

    def send(self, command_value: int, wait_done: bool = True):
        if self.ser is None:
            return
        try:
            payload = f"{int(command_value)}\n".encode("utf-8")
            self.ser.write(payload)
            time.sleep(0.04)
            if wait_done:
                self._wait_done()
        except Exception as exc:
            print(f"Serial write failed: {exc}")

    def _wait_done(self):
        if self.ser is None:
            return
        deadline = time.time() + self.ack_timeout_s
        while time.time() < deadline:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip().lower()
                if not line:
                    continue
                if line == "done":
                    return
                print(f"Arduino: {line}")
        print("Warning: Arduino ack timeout (done not received)")

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass


class JoystickInput:
    def __init__(self):
        self.enabled = False
        self.joy = None
        if pygame is None:
            return
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
                self.enabled = True
                print(f"Joystick connected: {self.joy.get_name()}")
            else:
                print("No joystick found, keyboard controls only")
        except Exception as exc:
            print(f"Joystick init failed: {exc}")

    def get_delta(self, step: int):
        if not self.enabled:
            return 0, 0, 0

        pygame.event.pump()
        deadzone = 0.35
        x = self.joy.get_axis(0) if self.joy.get_numaxes() > 0 else 0.0
        y = self.joy.get_axis(1) if self.joy.get_numaxes() > 1 else 0.0
        z = self.joy.get_axis(2) if self.joy.get_numaxes() > 2 else 0.0

        dx = 0
        dy = 0
        dz = 0

        if abs(x) > deadzone:
            dx = int(np.sign(x) * step)
        if abs(y) > deadzone:
            dy = int(np.sign(y) * step)
        if abs(z) > deadzone:
            dz = int(np.sign(z) * step)

        return dx, dy, dz

    def close(self):
        if pygame is not None:
            try:
                pygame.joystick.quit()
                pygame.quit()
            except Exception:
                pass


def mouse_callback(event, x, y, flags, state):
    del flags
    if event == cv2.EVENT_MOUSEMOVE:
        state["hover_square"] = find_square(x, y, state["sq_points"])
    if event == cv2.EVENT_LBUTTONDOWN:
        chosen = find_square(x, y, state["sq_points"])
        if chosen is not None:
            state["selected_square"] = chosen
            print(f"Selected square: {chosen}")


def main():
    parser = argparse.ArgumentParser(description="Map chess squares to servo angles using camera + manual control")
    parser.add_argument("--camera", type=int, default=1, help="Camera index")
    parser.add_argument("--port", type=str, default="COM4", help="Arduino serial port")
    parser.add_argument("--baud", type=int, default=9600, help="Arduino baud rate")
    parser.add_argument("--step", type=int, default=1, help="Servo angle step per input")
    parser.add_argument("--sqdict", type=str, default="sqdict.json", help="Path to sqdict.json")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output JSON file")
    args = parser.parse_args()

    sq_points = load_sq_points(Path(args.sqdict))
    output_path = Path(args.output)

    if output_path.exists():
        with open(output_path, "r") as fp:
            try:
                mapping = {str(k).upper(): v for k, v in json.load(fp).items()}
                print(f"Loaded existing mapping with {len(mapping)} entries")
            except Exception:
                mapping = {}
    else:
        mapping = {}

    bridge = ArduinoBridge(args.port, args.baud)
    joystick = JoystickInput()

    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Could not open camera at index 1")
        bridge.close()
        joystick.close()
        return

    servo1 = 90
    servo2 = 90
    servo3 = 90

    state = {
        "sq_points": sq_points,
        "hover_square": None,
        "selected_square": None,
    }

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback, state)

    # Move to initial state
    bridge.send(servo1)
    bridge.send(servo2 + 200)
    bridge.send(servo3 + 400)

    last_joy_update = 0.0
    joy_interval = 0.08

    print("Controls:")
    print("- Mouse click on square: select board position string")
    print("- Arrow keys or WASD: adjust servo1 and servo2")
    print("  left/right => servo1, up/down => servo2")
    print("- z/x: adjust servo3 (base)")
    print("- c: capture selected square -> [servo1, servo2, servo3]")
    print("- b: capture DISCARD/BIN pose")
    print("- j: save JSON now")
    print("- q: quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera frame read failed")
            break

        draw_outlines(sq_points, frame, show_text=True)

        selected = state["selected_square"]
        hover = state["hover_square"]
        status_square = selected if selected is not None else "NONE"

        text_lines = [
            f"Selected: {status_square}",
            f"Hover: {hover if hover else 'NONE'}",
            f"Servo1: {servo1}  Servo2: {servo2}  Servo3: {servo3}",
            f"Mapped entries: {len(mapping)}",
            "Keys: Arrows/WASD s1/s2 | z/x s3 | c capture | b discard | j save | q quit",
        ]

        y0 = 25
        for i, line in enumerate(text_lines):
            cv2.putText(frame, line, (10, y0 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 0), 2)

        cv2.imshow(WINDOW_NAME, frame)

        now = time.time()
        if now - last_joy_update > joy_interval:
            d1, d2, d3 = joystick.get_delta(args.step)
            if d1 != 0 or d2 != 0 or d3 != 0:
                old1, old2, old3 = servo1, servo2, servo3
                servo1 = clamp(servo1 + d1)
                servo2 = clamp(servo2 + d2)
                servo3 = clamp(servo3 + d3)
                if servo1 != old1:
                    bridge.send(servo1)
                if servo2 != old2:
                    bridge.send(servo2 + 200)
                if servo3 != old3:
                    bridge.send(servo3 + 400)
            last_joy_update = now

        key = cv2.waitKeyEx(1)

        if key == -1:
            continue

        if key == ord("q"):
            break

        # Servo1 controls (left/right + A/D)
        if key in (KEY_LEFT, ord("a"), ord("A")):
            servo1 = clamp(servo1 - args.step)
            bridge.send(servo1)
        elif key in (KEY_RIGHT, ord("d"), ord("D")):
            servo1 = clamp(servo1 + args.step)
            bridge.send(servo1)

        # Servo2 controls (up/down + W/S)
        elif key in (KEY_UP, ord("w"), ord("W")):
            servo2 = clamp(servo2 - args.step)
            bridge.send(servo2 + 200)
        elif key in (KEY_DOWN, ord("s"), ord("S")):
            servo2 = clamp(servo2 + args.step)
            bridge.send(servo2 + 200)

        # Servo3 controls (base)
        elif key in (ord("z"), ord("Z")):
            servo3 = clamp(servo3 - args.step)
            bridge.send(servo3 + 400)
        elif key in (ord("x"), ord("X")):
            servo3 = clamp(servo3 + args.step)
            bridge.send(servo3 + 400)

        elif key in (ord("c"), ord("C")):
            if selected is None:
                print("Select a square by clicking on the board first")
            else:
                mapping[selected] = [int(servo1), int(servo2), int(servo3)]
                with open(output_path, "w") as fp:
                    json.dump(mapping, fp, indent=2)
                write_arduino_header(mapping, ARDUINO_HEADER)
                print(f"Captured {selected}: {mapping[selected]}")

        elif key in (ord("b"), ord("B")):
            mapping["DISCARD"] = [int(servo1), int(servo2), int(servo3)]
            with open(output_path, "w") as fp:
                json.dump(mapping, fp, indent=2)
            write_arduino_header(mapping, ARDUINO_HEADER)
            print(f"Captured DISCARD pose: {mapping['DISCARD']}")

        elif key in (ord("j"), ord("J")):
            with open(output_path, "w") as fp:
                json.dump(mapping, fp, indent=2)
            write_arduino_header(mapping, ARDUINO_HEADER)
            print(f"Saved mapping to {output_path}")

    with open(output_path, "w") as fp:
        json.dump(mapping, fp, indent=2)
    write_arduino_header(mapping, ARDUINO_HEADER)
    print(f"Final mapping saved to {output_path}")

    cap.release()
    cv2.destroyAllWindows()
    bridge.close()
    joystick.close()


if __name__ == "__main__":
    main()
