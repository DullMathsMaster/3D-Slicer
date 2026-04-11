import uasyncio as asyncio
from machine import Pin

# Motor pins
m1_pins = [Pin(4, Pin.OUT), Pin(3, Pin.OUT), Pin(2, Pin.OUT), Pin(1, Pin.OUT)]
m2_pins = [Pin(15, Pin.OUT), Pin(14, Pin.OUT), Pin(13, Pin.OUT), Pin(12, Pin.OUT)]

# Buttons
btn_both_cw  = Pin(16, Pin.IN, Pin.PULL_DOWN)
btn_both_ccw = Pin(17, Pin.IN, Pin.PULL_DOWN)
calibrate    = Pin(18, Pin.IN, Pin.PULL_DOWN)

# Limit switches
lim_m1 = Pin(10, Pin.IN, Pin.PULL_DOWN)
lim_m2 = Pin(11, Pin.IN, Pin.PULL_DOWN)

step_sequence = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
]

STEPS_PER_PRESS = 256
STEP_DELAY_MS   = 1


async def step_motor(motor_pins, steps, direction, name, limit_btn, ignore_limit=False):
    step_index = 0
    for _ in range(steps):
        if not ignore_limit and limit_btn.value() == 1:
            for pin in motor_pins:
                pin.value(0)
            print(f"{name}: Limit reached, stopping")
            return True
        for i in range(4):
            motor_pins[i].value(step_sequence[step_index][i])
        step_index = (step_index + direction) % len(step_sequence)
        await asyncio.sleep_ms(STEP_DELAY_MS)
    for pin in motor_pins:
        pin.value(0)
    print(f"{name}: Done")
    return False


async def move_ccw_until_limit(motor_pins, limit_btn, name):
    step_index = 0
    while limit_btn.value() == 0:
        for i in range(4):
            motor_pins[i].value(step_sequence[step_index][i])
        step_index = (step_index - 1) % len(step_sequence)
        await asyncio.sleep_ms(STEP_DELAY_MS)
    for pin in motor_pins:
        pin.value(0)
    print(f"{name}: Limit hit")


async def move_cw_until_limit_released(motor_pins, limit_btn, name):
    step_index = 0
    while limit_btn.value() == 1:
        for i in range(4):
            motor_pins[i].value(step_sequence[step_index][i])
        step_index = (step_index + 1) % len(step_sequence)
        await asyncio.sleep_ms(STEP_DELAY_MS)
    for pin in motor_pins:
        pin.value(0)
    print(f"{name}: Limit released")


async def run_calibration():
    print("Calibration: moving both motors CCW to limits...")
    # Both move CCW simultaneously; each stops independently when its own limit is hit
    await asyncio.gather(
        move_ccw_until_limit(m1_pins, lim_m1, "Motor 1"),
        move_ccw_until_limit(m2_pins, lim_m2, "Motor 2")
    )
    print("Calibration: moving both motors CW until limits release...")
    # Both move CW simultaneously; each stops independently when its own limit releases
    await asyncio.gather(
        move_cw_until_limit_released(m1_pins, lim_m1, "Motor 1"),
        move_cw_until_limit_released(m2_pins, lim_m2, "Motor 2")
    )
    print("Calibration complete.")


async def main():
    print("System ready. Press buttons to move motors.")
    while True:
        if calibrate.value() == 1:
            await run_calibration()
        elif btn_both_ccw.value() == 1:
            print("Both motors: CCW")
            await asyncio.gather(
                step_motor(m1_pins, STEPS_PER_PRESS, -1, "Motor 1", lim_m1),
                step_motor(m2_pins, STEPS_PER_PRESS, -1, "Motor 2", lim_m2)
            )
        elif btn_both_cw.value() == 1:
            print("Both motors: CW")
            await asyncio.gather(
                step_motor(m1_pins, STEPS_PER_PRESS, 1, "Motor 1", lim_m1, ignore_limit=True),
                step_motor(m2_pins, STEPS_PER_PRESS, 1, "Motor 2", lim_m2, ignore_limit=True)
            )
        await asyncio.sleep_ms(10)


asyncio.run(main())