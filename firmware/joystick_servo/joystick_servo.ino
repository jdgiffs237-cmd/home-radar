// joystick_servo -- drive the SG90 by hand with the kit's joystick module.
//
// Push the stick right, the servo walks right. Push left, it walks left.
// Let go and it stays where it is. The further you push, the faster it moves.
//
// Wiring (same rails as the radar; the sensor can stay plugged in, it's ignored):
//   Joystick: GND -> blue rail, +5V -> red rail, VRx -> A0   (VRy and SW unused)
//   Servo:    orange -> D9, red -> red rail, brown -> blue rail
//
// If your servo moves the wrong way, flip JOY_DIRECTION to -1.
// Keep hands OFF the stick for the first second after power-up: it measures
// the stick's resting value then. Re-upload radar_joystick.ino for the radar.

#include <Servo.h>

const int SERVO_PIN = 9;
const int JOY_X_PIN = A0;

const int JOY_DIRECTION = 1;   // set to -1 if push-right moves the servo left
const int DEADZONE = 60;       // how far off-center the stick must be to count
const float MAX_SPEED = 2.0;   // degrees per step at full push

Servo servo;
float angle = 90.0;            // start centered
int joyCenter = 512;           // stick's resting reading, measured at boot

void setup() {
  servo.attach(SERVO_PIN);
  servo.write((int)angle);

  // The "centered" reading is half the stick's supply voltage, so it depends on
  // what powers it. Measure it instead of assuming 512; ignore a nonsense value
  // (stick held at boot) and fall back to 512.
  long sum = 0;
  for (int i = 0; i < 16; i++) { sum += analogRead(JOY_X_PIN); delay(5); }
  int measured = sum / 16;
  joyCenter = (measured > 400 && measured < 624) ? measured : 512;
}

void loop() {
  // The stick's X axis reads 0 (full left) to 1023 (full right), joyCenter at rest.
  int x = analogRead(JOY_X_PIN);
  int push = x - joyCenter;

  if (abs(push) > DEADZONE) {
    angle += JOY_DIRECTION * (push / 512.0) * MAX_SPEED;
    angle = constrain(angle, 0.0, 180.0);
    servo.write((int)angle);
  }

  delay(15);   // ~66 updates per second -- smooth but not jittery
}
