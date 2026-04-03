#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import threading

# --- Pins ---
MOTOR_X_PINS = [17, 18, 27, 22]
MOTOR_Y_PINS = [5, 6, 13, 19]

X_LIMIT   = 23
Y_LIMIT   = 25

BTN_X_CW  = 12
BTN_X_CCW = 16
BTN_Y_CW  = 20
BTN_Y_CCW = 21

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

for pin in [X_LIMIT, Y_LIMIT, BTN_X_CW, BTN_X_CCW, BTN_Y_CW, BTN_Y_CCW]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- Motor Controller ---
class MotorController:
    CW  =  1
    CCW = -1

    def __init__(self, name, pins, limit_pin):
        self.name             = name
        self.pins             = pins
        self.limit_pin        = limit_pin
        self._step_idx        = 0
        self._steps_from_bound = 0
        self._running         = False
        self._direction       = 0
        self._thread          = None
        self._lock            = threading.Lock()

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

    def _run(self):
        while self._running:
            if self._direction == self.CCW:
                if self._at_limit():
                    self._steps_from_bound = 0
                    print(f"[Motor {self.name}] Limit reached, stopping CCW")
                    self._running = False
                    break
            elif self._direction == self.CW:
                if self._steps_from_bound >= MAX_ROTATIONS * STEPS_PER_REV:
                    print(f"[Motor {self.name}] {MAX_ROTATIONS}-rotation cap reached, stopping CW")
                    self._running = False
                    break
            self._do_step(self._direction)
            time.sleep(STEP_DELAY)
        self._release_coils()

    def start(self, direction):
        with self._lock:
            if direction == self.CCW and self._at_limit():
                print(f"[Motor {self.name}] CCW blocked – limit switch active")
                return
            if direction == self.CW and self._steps_from_bound >= MAX_ROTATIONS * STEPS_PER_REV:
                print(f"[Motor {self.name}] CW blocked – rotation cap reached")
                return
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            self._direction = direction
            self._running   = True
            self._thread    = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._release_coils()

# --- Instantiate ---
motor_x = MotorController("X", MOTOR_X_PINS, X_LIMIT)
motor_y = MotorController("Y", MOTOR_Y_PINS, Y_LIMIT)

# --- Button Callbacks ---
_BUTTON_MAP = {
    BTN_X_CW:  (motor_x, MotorController.CW),
    BTN_X_CCW: (motor_x, MotorController.CCW),
    BTN_Y_CW:  (motor_y, MotorController.CW),
    BTN_Y_CCW: (motor_y, MotorController.CCW),
}

def _btn_event(channel):
    motor, direction = _BUTTON_MAP[channel]
    if GPIO.input(channel) == GPIO.LOW:
        motor.start(direction)
    else:
        motor.stop()

for btn_pin in _BUTTON_MAP:
    GPIO.add_event_detect(btn_pin, GPIO.BOTH, callback=_btn_event, bouncetime=50)

# --- Main ---
print("X-Y Rack Controller – Raspberry Pi 2B")
print(f"X CW: GPIO {BTN_X_CW} | X CCW: GPIO {BTN_X_CCW} | Limit: GPIO {X_LIMIT}")
print(f"Y CW: GPIO {BTN_Y_CW} | Y CCW: GPIO {BTN_Y_CCW} | Limit: GPIO {Y_LIMIT}")
print(f"Max CW rotations from bound: {MAX_ROTATIONS} | Ctrl-C to exit\n")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nShutting down...")
finally:
    motor_x.stop()
    motor_y.stop()
    GPIO.cleanup()
    print("GPIO cleaned up.")