# ChessBot-V2
# ChessBot V2

A physical chess-playing robot that combines a 3-DOF robotic arm, computer vision, and the Stockfish chess engine to play chess autonomously against a human opponent.

---

## How It Works

1. **Stockfish** calculates the best move for the computer.
2. **The robotic arm** (controlled via Arduino over serial) physically picks up and moves chess pieces using inverse kinematics.
3. **Computer vision** (OpenCV) watches the board via a webcam to detect the human player's move between frames.

---

## Hardware Requirements

- 3-DOF robotic arm with 4 servo motors:
  - Shoulder servo → Arduino pin 8 (270° Sunfounder)
  - Elbow servo → Arduino pin 9 (270° Sunfounder)
  - Base servo → Arduino pin 10 (180° MicroServo)
  - Gripper servo → Arduino pin 11 (180° MicroServo)
- Arduino board connected via USB (default port: `COM4`)
- Webcam (default: device index `2` for CV mode, `1` for calibration)
- Windows PC (Stockfish binary is the Windows AVX2 build)

---

## Project Structure

```
ChessBot-V2-main/
│
├── basic.py                          # Live keyboard control of servos (for testing/manual control)
├── README.md
│
└── ChessBot/
    └── ChessRobotArm/
        │
        ├── requirements.txt          # Python dependencies
        ├── sqdict.json               # Pre-calibrated board square → pixel polygon map
        ├── gridbuilder.py            # Tool to generate sqdict.json via webcam calibration
        ├── hough.py                  # Hough-transform based board detection (experimental)
        ├── verticalcam.py            # Vertical camera perspective utility
        ├── trial1(without colour).py # Early prototype: grayscale detection
        ├── trial2(withcolour).py     # Early prototype: colour-based detection
        │
        ├── src/
        │   ├── main.py               # ★ Main entry point — full game with computer vision
        │   ├── game.py               # Simplified game loop — no computer vision (manual input)
        │   ├── arm.py                # ChessRobotArm class — inverse kinematics + serial control
        │   ├── map_servo_angles.py   # Utility to manually map and calibrate servo angles per square
        │   ├── main_new.py           # Extended main with additional move-detection logic
        │   ├── main_1.py             # Alternate main variant
        │   ├── final_basic.py        # Simplified standalone arm control script
        │   ├── sqdict.json           # Square-to-pixel map used at runtime
        │   └── servo_angles.json     # Saved servo angle calibration data
        │
        ├── stockfish/
        │   └── stockfish-windows-2022-x86-64-avx2.exe   # Stockfish chess engine binary
        │
        └── src/arduino/controller/
            ├── controller.ino              # Legacy sketch (kept for reference, disabled)
            ├── main_move_controller.ino    # ★ Active sketch — handles serial move commands
            ├── mapper_controller.ino       # Sketch for servo angle mapping/calibration mode
            └── servo_angles_data.h         # Stored servo angle lookup table (header file)
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r ChessBot/ChessRobotArm/requirements.txt
```

### 2. Flash the Arduino

Open `src/arduino/controller/` in the Arduino IDE and upload **`main_move_controller.ino`** to your board. Do not upload `controller.ino` — it is disabled with `#if 0` and kept for reference only.

### 3. Configure ports and paths

Update the following hardcoded values before running:

| File | Variable | Default | Change to |
|---|---|---|---|
| `src/main.py` | Stockfish path | `C:\Users\KISHORE S\Desktop\...` | Your local path to `stockfish-windows-2022-x86-64-avx2.exe` |
| `src/main.py` | Serial port | `COM4` | Your Arduino's COM port |
| `src/game.py` | Stockfish path | `stockfish\stockfish-windows-2022-x86-64-avx2.exe` | Your local path |
| `src/game.py` | Serial port | `COM4` | Your Arduino's COM port |
| `basic.py` | `PORT` | `COM4` | Your Arduino's COM port |

### 4. Calibrate the board (first-time only)

Run `gridbuilder.py` to map each of the 64 squares to pixel coordinates on your webcam feed:

```bash
python ChessBot/ChessRobotArm/gridbuilder.py
```

- Click 4 corners per square in order: **TL → TR → BR → BL**
- Press `S` to save the result as `sqdict.json`
- Press `U` to undo the last square, `R` to reset all, `Q` to quit

Copy the generated `sqdict.json` into `src/` to use it with `main.py`.

---

## Running

### Full game with computer vision

```bash
cd ChessBot/ChessRobotArm/src
python main.py
```

The robot plays as White. After each robot move, press `R` to capture the board state before and after your move to detect it automatically.

**Keyboard shortcuts during play:**

| Key | Action |
|---|---|
| `R` | Capture a frame (press once before your move, once after) |
| `M` | Register Black castles kingside (e8g8) manually |
| `N` | Register Black castles queenside (e8c8) manually |
| `Q` | Quit |

### Simple game without computer vision

```bash
cd ChessBot/ChessRobotArm/src
python game.py
```

The robot moves automatically; you type your moves in UCI format (e.g. `e2e4`) into the terminal.

### Manual servo control (testing)

```bash
python basic.py
```

| Key | Servo | Direction |
|---|---|---|
| W / S | Shoulder (pin 8) | Up / Down |
| A / D | Elbow (pin 9) | Up / Down |
| I / K | Base (pin 10) | Right / Left |
| J / L | Gripper (pin 11) | Close / Open |
| Q | — | Quit |

---

## Key Components

### `src/arm.py` — `ChessRobotArm` class

The core robotics module. Handles:
- Serial communication with the Arduino
- **Inverse kinematics** to convert a chess square name (e.g. `e4`) into shoulder/elbow/base angles
- High-level actions: `move(sq1, sq2)`, `discard(sq)`, `grasp()`, `drop()`, `rest()`
- Knight moves use a separate `grasp_knight()` method due to piece height

Instantiate with arm segment lengths and the serial port:
```python
robot = ChessRobotArm(22, 22.5, port='COM4')
```

### `stockfish/stockfish-windows-2022-x86-64-avx2.exe`

The Stockfish 15 engine binary for Windows x86-64 with AVX2. Used via the `chess.engine` UCI interface. Move time is randomised slightly (`random.random()` seconds) to vary play strength and speed.

---


---

## Notes

- The Stockfish binary is Windows-only. On Linux/macOS, replace it with the appropriate build and update the path in `main.py` / `game.py`.
- `sqdict.json` at the project root and the one inside `src/` are separate files — `main.py` loads from the `src/` directory. Make sure to update the one in `src/` after calibration.
- `main_new.py`, `main_1.py`, and the trial scripts are development/experimental versions and are not needed for normal operation.
