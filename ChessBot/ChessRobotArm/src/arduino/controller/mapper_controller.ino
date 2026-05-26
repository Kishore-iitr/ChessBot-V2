#include <Servo.h>

#ifndef CHESSBOT_BUILD_MAPPER
#define CHESSBOT_BUILD_MAPPER 1
#endif

#if CHESSBOT_BUILD_MAPPER

// Calibration controller for map_servo_angles.py
// Protocol over Serial (newline-terminated integer commands):
// 0..180   -> shoulder logical angle
// 200..380 -> elbow logical angle (value - 200)
// 400..580 -> base angle (value - 400)
// 190      -> rest pose
// 191      -> close gripper
// 192      -> open gripper
// 193      -> close gripper for knight
// Responds with: done

Servo shoulder;
Servo elbow;
Servo base;
Servo gripper;

const int SHOULDER_PIN = 8;
const int ELBOW_PIN = 9;
const int BASE_PIN = 10;
const int GRIPPER_PIN = 11;

float toShoulderServo(float logicalAngle) {
  float adjusted = logicalAngle + 12.0;          // same compensation as main controller
  return (180.0 * adjusted) / 270.0;             // 270-degree shoulder servo
}

float toElbowServo(float logicalAngle) {
  float adjusted = logicalAngle + 3.0;           // same compensation as main controller
  return (180.0 * adjusted) / 270.0;             // 270-degree elbow servo
}

float toBaseServo(float angle) {
  return angle + 12.0;                           // same compensation as main controller
}

void shoulderTo(float logicalAngle) {
  float target = toShoulderServo(logicalAngle);
  float pos = shoulder.read();
  if (pos <= target) {
    for (; pos <= target; pos += 1) {
      shoulder.write(pos);
      delay(24);
    }
  } else {
    for (; pos >= target; pos -= 1) {
      shoulder.write(pos);
      delay(24);
    }
  }
}

void elbowTo(float logicalAngle) {
  float target = toElbowServo(logicalAngle);
  float pos = elbow.read();
  if (pos <= target) {
    for (; pos <= target; pos += 1) {
      elbow.write(pos);
      delay(20);
    }
  } else {
    for (; pos >= target; pos -= 1) {
      elbow.write(pos);
      delay(20);
    }
  }
}

void baseTo(float angle) {
  float target = toBaseServo(angle);
  float pos = base.read();
  if (pos <= target) {
    for (; pos <= target; pos += 1) {
      base.write(pos);
      delay(20);
    }
  } else {
    for (; pos >= target; pos -= 1) {
      base.write(pos);
      delay(20);
    }
  }
}

void gripperTo(float target) {
  float pos = gripper.read();
  if (pos <= target) {
    for (; pos <= target; pos += 1) {
      gripper.write(pos);
      delay(10);
    }
  } else {
    for (; pos >= target; pos -= 1) {
      gripper.write(pos);
      delay(10);
    }
  }
}

void rest() {
  shoulderTo(120);
  elbowTo(40);
}

void grasp() {
  gripperTo(75);
}

void graspKnight() {
  gripperTo(50);
}

void drop() {
  gripperTo(145);
}

void processCommand(long cmd) {
  if (cmd == 190) {
    rest();
  } else if (cmd == 191) {
    grasp();
  } else if (cmd == 192) {
    drop();
  } else if (cmd == 193) {
    graspKnight();
  } else if (cmd >= 0 && cmd <= 180) {
    shoulderTo((float)cmd);
  } else if (cmd >= 200 && cmd <= 380) {
    elbowTo((float)(cmd - 200));
  } else if (cmd >= 400 && cmd <= 580) {
    baseTo((float)(cmd - 400));
  }
}

void setup() {
  Serial.begin(9600);

  shoulder.attach(SHOULDER_PIN);
  elbow.attach(ELBOW_PIN);
  base.attach(BASE_PIN);
  gripper.attach(GRIPPER_PIN);

//   gripper.write(70);
  base.write(100);
  delay(500);
  rest();
  drop();

  Serial.println("init");
  Serial.println("done");
}

void loop() {
  if (Serial.available() <= 0) {
    return;
  }

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) {
    return;
  }

  long cmd = line.toInt();
  processCommand(cmd);
  Serial.println("done");
}

#endif
