#ifndef CHESSBOT_BUILD_MAPPER
#define CHESSBOT_BUILD_MAPPER 1
#endif

#if !CHESSBOT_BUILD_MAPPER

#include <Servo.h>

#include "servo_angles_data.h"

// Main chess-move controller for the robot arm.
// Python sends commands like:
//   MOVE e2e4
//   MOVE d5e6 CAPTURE d5
//   MOVE e1g1
// The Arduino looks up square poses from servo_angles_data.h, then moves the arm.
// Reply over Serial: done

typedef SquarePose Pose;

Servo shoulder;
Servo elbow;
Servo base;
Servo gripper;

const int SHOULDER_PIN = 8;
const int ELBOW_PIN = 9;
const int BASE_PIN = 10;
const int GRIPPER_PIN = 11;

float toShoulderServo(float logicalAngle) {
  float adjusted = logicalAngle + 12.0;
  return (180.0 * adjusted) / 270.0;
}

float toElbowServo(float logicalAngle) {
  float adjusted = logicalAngle + 3.0;
  return (180.0 * adjusted) / 270.0;
}

float toBaseServo(float angle) {
  return angle + 12.0;
}

void moveServoSmooth(Servo &s, float target, int stepDelayMs) {
  float pos = s.read();
  if (pos <= target) {
    for (; pos <= target; pos += 1) {
      s.write(pos);
      delay(stepDelayMs);
    }
  } else {
    for (; pos >= target; pos -= 1) {
      s.write(pos);
      delay(stepDelayMs);
    }
  }
}

void shoulderTo(float logicalAngle) {
  moveServoSmooth(shoulder, toShoulderServo(logicalAngle), 24);
}

void elbowTo(float logicalAngle) {
  moveServoSmooth(elbow, toElbowServo(logicalAngle), 20);
}

void baseTo(float angle) {
  moveServoSmooth(base, toBaseServo(angle), 20);
}

void gripperTo(float target) {
  moveServoSmooth(gripper, target, 10);
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

bool lookupPose(const String &square, Pose &pose) {
  String target = square;
  target.toUpperCase();

  for (size_t i = 0; i < SQUARE_POSES_COUNT; ++i) {
    if (target.equalsIgnoreCase(SQUARE_POSES[i].square)) {
      pose.servo1 = SQUARE_POSES[i].servo1;
      pose.servo2 = SQUARE_POSES[i].servo2;
      pose.servo3 = SQUARE_POSES[i].servo3;
      return true;
    }
  }
  return false;
}

bool lookupDiscardPose(Pose &pose) {
  return lookupPose("DISCARD", pose);
}

void goToPose(const Pose &pose) {
  shoulderTo(pose.servo1);
  elbowTo(pose.servo2);
  baseTo(pose.servo3);
}

void goToSquareAndGrasp(const Pose &pose) {
  gripperTo(145);
  goToPose(pose);
  gripperTo(75);
  rest();
}

void goToSquareAndRelease(const Pose &pose) {
  goToPose(pose);
  gripperTo(145);
  rest();
}

void moveCapturedPieceToDiscard(const Pose &capturePose, const Pose &discardPose) {
  gripperTo(145);
  goToPose(capturePose);
  gripperTo(75);
  goToPose(discardPose);
  gripperTo(145);
  rest();
}

bool executeSimpleMove(const String &sourceSquare, const String &targetSquare) {
  Pose sourcePose;
  Pose targetPose;

  if (!lookupPose(sourceSquare, sourcePose)) {
    Serial.print("unknown source: ");
    Serial.println(sourceSquare);
    return false;
  }
  if (!lookupPose(targetSquare, targetPose)) {
    Serial.print("unknown target: ");
    Serial.println(targetSquare);
    return false;
  }

  goToSquareAndGrasp(sourcePose);
  goToSquareAndRelease(targetPose);
  return true;
}

bool executeMove(const String &move, const String &captureSquare) {
  if (move.length() < 4) {
    return false;
  }

  String sourceSquare = move.substring(0, 2);
  String targetSquare = move.substring(2, 4);
  String normalizedMove = move;
  normalizedMove.toLowerCase();

  Pose sourcePose;
  Pose targetPose;
  if (!lookupPose(sourceSquare, sourcePose) || !lookupPose(targetSquare, targetPose)) {
    Serial.println("pose lookup failed");
    return false;
  }

  if (captureSquare.length() >= 2) {
    Pose capturePose;
    Pose discardPose;
    if (!lookupPose(captureSquare, capturePose)) {
      Serial.println("capture lookup failed");
      return false;
    }
    if (!lookupDiscardPose(discardPose)) {
      Serial.println("discard lookup failed");
      return false;
    }
    moveCapturedPieceToDiscard(capturePose, discardPose);
  }

  goToSquareAndGrasp(sourcePose);
  goToSquareAndRelease(targetPose);

  if (normalizedMove == "e1g1") {
    executeSimpleMove("h1", "f1");
  } else if (normalizedMove == "e1c1") {
    executeSimpleMove("a1", "d1");
  } else if (normalizedMove == "e8g8") {
    executeSimpleMove("h8", "f8");
  } else if (normalizedMove == "e8c8") {
    executeSimpleMove("a8", "d8");
  }

  return true;
}

void setup() {
  Serial.begin(9600);

  shoulder.attach(SHOULDER_PIN);
  elbow.attach(ELBOW_PIN);
  base.attach(BASE_PIN);
  gripper.attach(GRIPPER_PIN);

  gripper.write(70);
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

  if (!line.startsWith("MOVE ")) {
    Serial.println("done");
    return;
  }

  String payload = line.substring(5);
  payload.trim();

  String move = payload;
  String captureSquare = "";

  int captureIndex = payload.indexOf("CAPTURE ");
  if (captureIndex >= 0) {
    move = payload.substring(0, captureIndex);
    move.trim();
    captureSquare = payload.substring(captureIndex + 8);
    captureSquare.trim();
    captureSquare = captureSquare.substring(0, 2);
  }

  executeMove(move, captureSquare);
  Serial.println("done");
}

#endif
