#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time

# --- Pins ---
MOTOR_X_PINS = [2, 3, 4, 14]
MOTOR_Y_PINS = [15, 18, 17, 27]

X_LIMIT     = 22
Y_LIMIT     = 23

CALIBRATE_Z = 10
Z_DOWN      = 9
Z_UP        = 11

# --- Constants ---
MAX_ROTATIONS = 80
STEPS_PER_REV = 4096
STEP_DELAY    = 0.0005

HALF_STEP_SEQ = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
]

# --- GPIO Setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in MOTOR_X_PINS + MOTOR_Y_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

for pin in [X_LIMIT, Y_LIMIT]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

for pin in [CALIBRATE_Z, Z_DOWN, Z_UP]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# --- Motor Controller ---
class MotorController:
    CW  =  1
    CCW = -1

    def __init__(self, name, pins, limit_pin):
        self.name              = name
        self.pins              = pins
        self.limit_pin         = limit_pin
        self._step_idx         = 0
        self._steps_from_bound = 0

    def _at_limit(self):
        return GPIO.input(self.limit_pin) == GPIO.LOW

    def _set_coils(self, row):
        for pin, val in zip(self.pins, row):
            GPIO.output(pin, val)

    def _release_coils(self):
        for pin in self.pins:
            GPIO.output(pin, GPIO.LOW)

    def _do_step(self, direction):
        self._step_idx = (self._step_idx + direction) % len(HALF_STEP_SEQ)
        self._set_coils(HALF_STEP_SEQ[self._step_idx])
        if direction == self.CW:
            self._steps_from_bound += 1
        else:
            self._steps_from_bound = max(0, self._steps_from_bound - 1)

    def move(self, direction, steps):
        label = "forward" if direction == self.CW else "backward"
        print(f"[Motor {self.name}] {label} {steps / STEPS_PER_REV:.2f} turns ({steps} steps)...")
        try:
            for _ in range(steps):
                if direction == self.CCW and self._at_limit():
                    self._steps_from_bound = 0
                    print(f"[Motor {self.name}] Limit reached, stopping early")
                    break
                if direction == self.CW and self._steps_from_bound >= MAX_ROTATIONS * STEPS_PER_REV:
                    print(f"[Motor {self.name}] {MAX_ROTATIONS}-rotation cap reached, stopping early")
                    break
                self._do_step(direction)
                time.sleep(STEP_DELAY)
        finally:
            self._release_coils()
        print(f"[Motor {self.name}] Done")

    def calibrate(self):
        print(f"[Motor {self.name}] Calibrating – moving forward until limit...")
        try:
            while not self._at_limit():
                self._do_step(self.CW)
                time.sleep(STEP_DELAY)
        finally:
            self._release_coils()
        print(f"[Motor {self.name}] Limit hit – backing off...")
        try:
            while self._at_limit():
                self._do_step(self.CCW)
                time.sleep(STEP_DELAY)
        finally:
            self._release_coils()
        self._steps_from_bound = 0
        print(f"[Motor {self.name}] Calibration complete")

# --- Z-axis signal to Pico ---
def pulse_pin(pin, duration=0.4):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(pin, GPIO.LOW)

# --- Instantiate ---
motor_x = MotorController("X", MOTOR_X_PINS, X_LIMIT)
motor_y = MotorController("Y", MOTOR_Y_PINS, Y_LIMIT)

# --- Command Parser ---
def parse_command(cmd):
    parts = cmd.strip().lower().split()
    if not parts:
        return

    if parts[0] == "up":
        print("Signalling Pico: UP")
        pulse_pin(Z_UP)
        return

    if parts[0] == "down":
        print("Signalling Pico: DOWN")
        pulse_pin(Z_DOWN)
        return

    if parts[0] == "calibrate":
        if len(parts) == 1:
            print("Signalling Pico: CALIBRATE")
            pulse_pin(CALIBRATE_Z)
        elif parts[1] == "x":
            motor_x.calibrate()
        elif parts[1] == "y":
            motor_y.calibrate()
        else:
            print("Usage: calibrate | calibrate x | calibrate y")
        return

    if parts[0] in ("x", "y"):
        if len(parts) != 3:
            print("Usage: x/y forward/backward <turns>")
            return
        motor = motor_x if parts[0] == "x" else motor_y
        if parts[1] == "forward":
            direction = MotorController.CW
        elif parts[1] == "backward":
            direction = MotorController.CCW
        else:
            print("Direction must be 'forward' or 'backward'")
            return
        try:
            turns = float(parts[2])
            if turns <= 0:
                raise ValueError
        except ValueError:
            print("Turns must be a positive number e.g. 2.1")
            return
        motor.move(direction, int(turns * STEPS_PER_REV))
        return

    print(f"Unknown command: '{cmd}'")
    print("Commands: x/y forward/backward <turns> | calibrate [x|y] | up | down")

# --- Main ---
print("X-Y Rack Controller – Raspberry Pi 2B")
print(f"X Limit: GPIO {X_LIMIT} | Y Limit: GPIO {Y_LIMIT}")
print(f"Z Calibrate: GPIO {CALIBRATE_Z} | Z Down: GPIO {Z_DOWN} | Z Up: GPIO {Z_UP}")
print("Commands: x/y forward/backward <turns> | calibrate [x|y] | up | down")
print("Ctrl-C to exit\n")

try:
    while True:
        try:
            cmd = input("> ")
            parse_command(cmd)
        except EOFError:
            break
except KeyboardInterrupt:
    print("\nShutting down...")
finally:
    for pin in MOTOR_X_PINS + MOTOR_Y_PINS:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up.")