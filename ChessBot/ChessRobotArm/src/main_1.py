# Play a full game using Computer Vision

import os
import random
import subprocess
import sys
import threading
import time
from queue import Empty, Queue

import chess
import chess.engine
from dotenv import load_dotenv


def log(msg):
    print(f"[main] {msg}", flush=True)


load_dotenv()
stockfish_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "stockfish",
        "stockfish-windows-2022-x86-64-avx2.exe",
    )
)
log(f"Loading Stockfish from: {stockfish_path}")
engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

camera_proc = None
camera_queue = Queue()
camera_reader = None


def _camera_reader_loop(proc, out_queue):
    if proc.stdout is None:
        out_queue.put("__CAMERA_EOF__")
        return
    for raw in proc.stdout:
        out_queue.put(raw.rstrip("\n"))
    out_queue.put("__CAMERA_EOF__")


def start_camera_process():
    global camera_proc, camera_reader
    if camera_proc is not None and camera_proc.poll() is None:
        return

    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trial1(without colour).py"))
    script_dir = os.path.dirname(script_path)
    cmd = [sys.executable, script_path]
    log(f"Starting persistent camera subprocess: {cmd}")
    camera_proc = subprocess.Popen(
        cmd,
        cwd=script_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    camera_reader = threading.Thread(
        target=_camera_reader_loop,
        args=(camera_proc, camera_queue),
        daemon=True,
    )
    camera_reader.start()


def _parse_camera_line_for_move(camera_line):
    if "Move finalised:" not in camera_line:
        return None
    parts = camera_line.split(":", 1)[-1].strip().replace(" ", "")
    if "->" not in parts:
        return None
    start, end = parts.split("->", 1)
    if len(start) == 2 and len(end) == 2:
        return start.lower() + end.lower()
    return None


def get_move_from_camera(max_wait_s=20.0):
    global camera_proc
    start_camera_process()
    if camera_proc is None:
        log("Camera subprocess is not available")
        return None

    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        try:
            camera_line = camera_queue.get(timeout=0.4)
        except Empty:
            if camera_proc.poll() is not None:
                log(f"Camera subprocess exited with code {camera_proc.returncode}")
                camera_proc = None
                return None
            continue

        if camera_line == "__CAMERA_EOF__":
            if camera_proc is not None:
                log(f"Camera subprocess exited with code {camera_proc.returncode}")
            camera_proc = None
            return None

        print(f"[camera] {camera_line}", flush=True)
        parsed = _parse_camera_line_for_move(camera_line)
        if parsed:
            log(f"Parsed FINALISED camera move: {parsed}")
            return parsed

    log("Camera timeout: no finalised move detected")
    return None


def get_manual_move_with_retry():
    move = input("Enter your move (e.g. b2b3), or press Enter to retry camera: ").strip().lower()
    if not move:
        return None
    if len(move) != 4:
        log("Invalid move format from manual input")
        return None
    return move


def stop_camera_process():
    global camera_proc
    if camera_proc is None:
        return
    if camera_proc.poll() is None:
        log("Stopping persistent camera subprocess")
        camera_proc.terminate()
        try:
            camera_proc.wait(timeout=2)
        except Exception:
            log("Force-killing persistent camera subprocess")
            camera_proc.kill()
    camera_proc = None


def main():
    camera_on = True
    log(f"CAMERA_ON resolved to: {camera_on}")
    board = chess.Board()
    log("Robot arm initialized")
    print("Starting Chess Game. Camera mode:", camera_on)

    try:
        if camera_on:
            start_camera_process()

        while not board.is_game_over():
            if camera_on:
                log("Waiting for finalised move from camera...")
                move = get_move_from_camera(max_wait_s=20.0)
                if not move:
                    log("No finalised move from camera. Falling back to manual input.")
                    move = get_manual_move_with_retry()
                    if not move:
                        log("No usable move available. Retrying turn.")
                        continue
            else:
                move = get_manual_move_with_retry()
                if not move:
                    log("No usable manual move. Retrying turn.")
                    continue

            try:
                log(f"Pushing player move to board: {move}")
                board.push_uci(move)
            except Exception as exc:
                log(f"Invalid move rejected by board: {exc}")
                continue

            print("You played:", move)
            log("Requesting engine move from Stockfish")
            result = engine.play(board, chess.engine.Limit(time=random.random()))
            engine_move = result.move.uci()
            log(f"Engine responded with move: {engine_move}")
            print("Engine plays:", engine_move)
            board.push(result.move)
            log("Engine move pushed to board")
            print(board)

        print("Game over.")
        log("Game loop ended")
    finally:
        stop_camera_process()
        engine.quit()
        log("Cleaned up camera subprocess and engine")


if __name__ == "__main__":
    main()