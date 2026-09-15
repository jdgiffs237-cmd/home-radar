// joystick_servo -- drive the SG90 by hand with the kit's joystick module.
//
// Push the stick right, the servo walks right. Push left, it walks left.
// Let go and it stays where it is. The further you push, the faster it moves.
//
// Wiring:
//   Joystick: GND -> GND, +5V -> 5V, VRx -> A0   (VRy and SW unused)
//   Servo:    orange -> D9, red -> 5V, brown -> GND
//
// If your servo moves the wrong way, flip JOY_DIRECTION to -1.
// When you're done playing, re-upload radar_sweep.ino to get the radar back.

#include <Servo.h>

const int SERVO_PIN = 9;
const int JOY_X_PIN = A0;

const int JOY_DIRECTION = 1;   // set to -1 if push-right moves the servo left
const int DEADZONE = 60;       // how far off-center the stick must be to count
const float MAX_SPEED = 2.0;   // degrees per step at full push

Servo servo;
float angle = 90.0;            // start centered

void setup() {
  servo.attach(SERVO_PIN);
  servo.write((int)angle);
}

void loop() {
  // The stick's X axis reads 0 (full left) to 1023 (full right), ~512 at rest.
  int x = analogRead(JOY_X_PIN);
  int push = x - 512;

  if (abs(push) > DEADZONE) {
    angle += JOY_DIRECTION * (push / 512.0) * MAX_SPEED;
    angle = constrain(angle, 0.0, 180.0);
    servo.write((int)angle);
  }

  delay(15);   // ~66 updates per second -- smooth but not jittery
}
