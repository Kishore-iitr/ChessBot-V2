import serial
import keyboard
import time
import sys

# --- CONFIGURATION ---
PORT = 'COM4'  # <--- CHANGE THIS TO YOUR ARDUINO PORT
BAUD = 9600

# Connect to the Arduino
try:
    print(f"Attempting to connect to Arduino on {PORT}...")
    arduino = serial.Serial(PORT, BAUD)
    time.sleep(2)  # Arduino resets when serial connects; give it 2 seconds to wake up
    print("Connected successfully!")
except serial.SerialException:
    print(f"Error: Could not find Arduino on {PORT}. Please check your port setting.")
    sys.exit()

print("""
=================================
      LIVE SERVO CONTROLS        
=================================
Servo 1 (Pin 8)  : S (Up) / W (Down)
Servo 2 (Pin 9)  : A (elbow up) / D (elbow down)
Servo 3 (Pin 10) : I(rotate right) / K (rotate left)
Servo 4 (Pin 11) : J (gripper close) / L (gripper open)

Press 'Q' to quit the program.
=================================a
""")

# We use a tiny delay so we don't spam the Arduino faster than it can move
delay = 0.05 

try:
    while True:
        # Servo 1 keys
        if keyboard.is_pressed('w'):
            arduino.write(b's')
            time.sleep(delay)
        elif keyboard.is_pressed('s'):
            arduino.write(b'w')
            time.sleep(delay)
            
        # Servo 2 keys
        elif keyboard.is_pressed('a'):
            arduino.write(b'k')
            time.sleep(delay)
        elif keyboard.is_pressed('d'):
            arduino.write(b'i')
            time.sleep(delay)
            
        # Servo 3 keys
        elif keyboard.is_pressed('i'):
            arduino.write(b'a')
            time.sleep(delay)
        elif keyboard.is_pressed('k'):
            arduino.write(b'd')
            time.sleep(delay)
            
        # Servo 4 keys
        elif keyboard.is_pressed('j'):
            arduino.write(b'j')
            time.sleep(delay)
        elif keyboard.is_pressed('l'):
            arduino.write(b'l')
            time.sleep(delay)
            
        # Quit key
        elif keyboard.is_pressed('q'):
            print("Shutting down connection...")
            break

except KeyboardInterrupt:
    print("\nProgram interrupted.")

finally:
    if 'arduino' in locals() and arduino.is_open:
        arduino.close()
        print("Disconnected from Arduino.")