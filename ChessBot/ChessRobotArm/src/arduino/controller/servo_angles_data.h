#pragma once

#include <Arduino.h>

struct SquarePose {
  const char* square;
  uint8_t servo1;
  uint8_t servo2;
  uint8_t servo3;
};

static const SquarePose SQUARE_POSES[] = {
  {"DISCARD", 80, 0, 180}
};

static const size_t SQUARE_POSES_COUNT = 1;
