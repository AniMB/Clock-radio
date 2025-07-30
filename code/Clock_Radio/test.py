from machine import I2C, Pin
from libraries.radio import Radio
import time

r = Radio(100.1, 60, 0)   # 60% volume, unmuted
print("Playing 100.1 MHz...")
time.sleep(5)

print("Mute 2s")
r.SetMute(1); r.ProgramRadio()
time.sleep(2)

print("Unmute and tune 101.9 MHz...")
r.SetFrequency(100.3)
r.SetVolume(50)
r.SetMute(0)
r.ProgramRadio()

while True:
    time.sleep(1)
