import json
import os
import sys
from machine import *
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer
from typing import Any
from config.resources import _lock
from network import WLAN, AP_IF
from ssd1306 import *



"""Make a read json write json function that uses a lock to ensure thread safety. This will be for the main.py file."""
class JsonHandler:
    def __init__(self):
        self.__filename = "database/web_data.json"
        self.__unsaved_local_changes = False
        self.json_object = {}

    def read_json(self) ->bool:
        if not self.__unsaved_local_changes:
            # Ensure thread safety when reading the JSON file
            self.__unsaved_local_changes = True       

            if _lock.acquire(blocking=False):

                try:
                    with open(self.__filename, 'r') as file:
                        self.json_object= json.load(file)  
                    
                    return True
                except FileNotFoundError:
                    print(f"File {self.__filename} not found.")
                    
                    return False
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from {self.__filename}: {e}")
                    return False
                finally:
                    _lock.release()
            else:
                print("Lock is already acquired, cannot read JSON file.")
                return False
        else:
            
            return True  # Return False if there are unsaved local changes

    def write_json(self) -> bool:
        if _lock.acquire(blocking=False):
            self.__unsaved_local_changes = False
            try:
                with open(self.__filename, 'w') as file:
                    json.dump(self.json_object, file, indent=4)  # type: ignore
                
                return True
            except Exception as e:
                print(f"Error writing to {self.__filename}: {e}")
                return False
            finally:
                _lock.release()
            
        else:
            print("Lock is already acquired, cannot write JSON file.")

            return False  


#define rotatory encoders and push buttons
# enc_pins = [
#         Pin(1,  Pin.IN, Pin.PULL_UP),
#         Pin(5,  Pin.IN, Pin.PULL_UP),
#         Pin(26, Pin.IN, Pin.PULL_UP)
# ]

# Rotary Encoder 1 Pins (connected to GP2, GP3, GP1)
encoder1A = Pin(3, Pin.IN, Pin.PULL_UP)    # ROT1A
encoder1B = Pin(2, Pin.IN, Pin.PULL_UP)    # ROT1B
encoder2SW = Pin(1, Pin.IN, Pin.PULL_UP)   # SW2

# Encoder 2 Pins (J5) mapped to GP4, GP5, GP6
encoder2A = Pin(6, Pin.IN, Pin.PULL_UP)    # RDT2A
encoder2B = Pin(7, Pin.IN, Pin.PULL_UP)    # RDT2B
encoder4SW = Pin(5, Pin.IN, Pin.PULL_UP)   # SW4

# Rotary Encoder 3 Pins (connected to GP26, GP27, GP28)
encoder3A = Pin(28, Pin.IN, Pin.PULL_UP)   # ROT3A
encoder3B = Pin(27, Pin.IN, Pin.PULL_UP)   # ROT3B
encoder3SW = Pin(26, Pin.IN, Pin.PULL_UP)  # SW3


encoder=[encoder2SW,encoder1A,encoder1B,
encoder2A,encoder2B,encoder4SW,
encoder3A,encoder3B,encoder3SW]


button=Pin(0, Pin.IN, Pin.PULL_UP)


#define display pins
spi_sck = Pin(18)
spi_sda = Pin(19)
spi_res = Pin(21)
spi_dc  = Pin(20)
spi_cs  = Pin(17)




class IdleMode:
    """
    Manages inactivity on rotary encoders + button,
    displays RTC time when idle, and cycles modes (1-3) on encoder1 rotation.
    OLED SPI/control pins are hardcoded for simplicity.
    """
    def __init__(
        self,
        encoder_pins,        # list of Pin objects: [enc1, enc2, enc3]
        button_pin,          # Pin object for push-button input (if any)
        spi_id=0,
        width=128,
        height=64,
        timeout_ms=3000
    ):
        # inactivity threshold (ms)
        self.timeout_ms = timeout_ms

        # Real Time Clock
        self.rtc = RTC()

        # OLED SPI and control pins (hardcoded)
        spi_sck = Pin(18)
        spi_mosi = Pin(19)
        spi_res = Pin(21)
        spi_dc  = Pin(20)
        spi_cs  = Pin(17)

        # initialize SPI and OLED display
        self.spi = SPI(spi_id, sck=spi_sck, mosi=spi_mosi, baudrate=100000)
        self.oled = SSD1306_SPI(width, height, self.spi, spi_dc, spi_res, spi_cs, reset=True)

        # inputs
        self.button = button_pin
        self.encoders = encoder_pins

        # internal state
        self.last_edge = ticks_ms()
        self.idle = False
        self.current_mode = 1  # current mode (1-3)

        # attach IRQ handlers: encoder edges and button press
        for enc in self.encoders:
            enc.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
                    handler=self._on_edge,
                    hard=True)
        self.button.irq(trigger=Pin.IRQ_FALLING,
                        handler=self._on_button,
                        hard=True)

        # watchdog timer: check for inactivity every 500 ms
        self._watchdog = Timer(-1)
        self._watchdog.init(period=500,
                             mode=Timer.PERIODIC,
                             callback=self._watchdog_cb)

        # display refresh: update clock once per second while idle
        self._refresh = Timer(-1)
        self._refresh.init(period=1000,
                            mode=Timer.PERIODIC,
                            callback=self._refresh_cb)

    def __repr__(self):
        """Return a developer-friendly representation of the IdleMode state."""
        return (f"<IdleMode(idle={self.idle}, current_mode={self.current_mode}, "
                f"is_24h={self.is_24h}, timeout_ms={self.timeout_ms})>")
        self._refresh.init(period=1000,
                            mode=Timer.PERIODIC,
                            callback=self._refresh_cb)

    def _on_edge(self, pin):
        """Encoder edge handler: resets inactivity; cycles mode on encoder1."""
        self.last_edge = ticks_ms()
        if self.idle:
            self.idle = False
            self.oled.fill(0)
            self.oled.show()
        if pin == self.encoders[0]:  # encoder1 rotated
            # cycle through modes 1->2->3
            self.current_mode = (self.current_mode % 3) + 1
            self.mode()  # display mode menu

    def _on_button(self, pin):
        """Button press handler: cycles mode and displays it."""
        if pin.value() == 0:
            self.current_mode = (self.current_mode % 3) + 1
            self.mode()
            self.last_edge = ticks_ms()

    def mode(self):
        """Display the mode selection prompt on the OLED."""
        # Show the selection menu for modes 1,2,3
        self.oled.fill(0)
        self.oled.text("Which Mode?", 0, 0)
        self.oled.text("1,2,3", 0, 10)
        self.oled.show()
        # Debug print the current mode
        print(f"→ Mode menu displayed. Current selection: {self.current_mode}")

    def _watchdog_cb(self, timer):
        """Watchdog: enter idle if no activity for timeout_ms."""
        diff = ticks_diff(ticks_ms(), self.last_edge)
        if diff >= self.timeout_ms and self.button.value() == 1:
            if not self.idle:
                self.idle = True
                self._display_time()
        else:
            if self.idle:
                self.idle = False
                self.oled.fill(0)
                self.oled.show()

    def _refresh_cb(self, timer):
        """Refresh display periodically when in idle state."""
        if self.idle:
            self._display_time()

    def _display_time(self):
        # reads RTC and displays in selected format
        _, _, _, _, h, m, s, _ = self.rtc.datetime()
        if self.is_24h:
            ts = f"{h:02}:{m:02}:{s:02}"
        else:
            suffix = "AM" if h < 12 else "PM"
            hour12 = h % 12 or 12
            ts = f"{hour12:02}:{m:02}:{s:02} {suffix}"
        self.oled.fill(0)
        self.oled.text(ts, 0, 0)
        self.oled.show()
        print(f"→ Idle time: {ts}")







class AlarmMode:
    """
    Manages alarm setting in two stages: hour then minute.
    Enter with .enter(), spin encoder1 to adjust values,
    stage transitions on 3s inactivity.
    """
    def __init__(
        self,
        encoder_pin,   # Pin object for encoder1
        oled,          # SSD1306_SPI instance
        rtc,           # RTC instance
        timeout_ms=3000,
        interval_ms=500
    ):
        self.encoder = encoder_pin
        self.oled = oled
        self.rtc = rtc
        self.timeout_ms = timeout_ms
        self.stage = 0  # 0=hour, 1=minute
        self.alarm_hour = 0
        self.alarm_minute = 0
        self.setting = False
        self.last_edge = ticks_ms()

        # inactivity timer
        self._timer = Timer(-1)
        self._timer.init(
            period=interval_ms,
            mode=Timer.PERIODIC,
            callback=self._check_timeout
        )
        # encoder IRQ
        self.encoder.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._on_edge,
            hard=True
        )

    def enter(self):
        """Begin alarm-setting: init values and display hour stage."""
        # load current RTC hour
        _, _, _, _, h, m, _, _ = self.rtc.datetime()
        self.alarm_hour = h
        self.alarm_minute = m
        self.stage = 0
        self.setting = True
        self.last_edge = ticks_ms()
        self._display_alarm()

    def _on_edge(self, pin):
        """Handle encoder rotations to adjust hour or minute."""
        if not self.setting or pin != self.encoder:
            return
        self.last_edge = ticks_ms()
        if self.stage == 0:
            # adjust hour
            self.alarm_hour = (self.alarm_hour + 1) % 24
        else:
            # adjust minute
            self.alarm_minute = (self.alarm_minute + 1) % 60
        self._display_alarm()

    def _check_timeout(self, t):
        """On inactivity, advance stage or exit setting."""
        if not self.setting:
            return
        if ticks_diff(ticks_ms(), self.last_edge) < self.timeout_ms:
            return
        if self.stage == 0:
            # move to minute setting
            self.stage = 1
            self.last_edge = ticks_ms()
            self._display_alarm()
        else:
            # finish setting
            self.setting = False
            self.oled.fill(0)
            self.oled.show()
            print(f"→ Alarm set: {self.alarm_hour:02}:{self.alarm_minute:02}")

    def _display_alarm(self):
        """Render the current alarm stage and value on the OLED."""
        self.oled.fill(0)
        if self.stage == 0:
            self.oled.text("Set Alarm Hour:", 0, 0)
            self.oled.text(f"{self.alarm_hour:02}:00", 0, 10)
            print(f"→ Setting hour: {self.alarm_hour:02}")
        else:
            self.oled.text("Set Alarm Minute:", 0, 0)
            self.oled.text(f":{self.alarm_minute:02}", 0, 10)
            print(f"→ Setting minute: {self.alarm_minute:02}")
        self.oled.show()

    def __repr__(self):
        """Return a developer‑friendly summary of the AlarmMode state."""
        return (f"<AlarmMode(setting={self.setting}, "
                f"stage={self.stage}, "
                f"hour={self.alarm_hour:02}, "
                f"minute={self.alarm_minute:02})>")




class ClockMode:
    """
    Manages clock-setting via encoder2: hour then minute.
    Enter with .enter(), spin encoder2 to adjust values,
    stage transitions on 3s inactivity, press encoder2 to exit.
    """
    def __init__(
        self,
        encoder_pin,
        oled,
        rtc,
        timeout_ms=3000,
        interval_ms=500
    ):
        self.encoder = encoder_pin
        self.oled = oled
        self.rtc = rtc
        self.timeout_ms = timeout_ms
        self.stage = 0
        self.new_hour = 0
        self.new_minute = 0
        self.setting = False
        self.last_edge = ticks_ms()
        self._timer = Timer(-1)
        self._timer.init(
            period=interval_ms,
            mode=Timer.PERIODIC,
            callback=self._check_timeout
        )
        self.encoder.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._on_edge,
            hard=True
        )
        self.encoder_press = self.encoder  # using same pin for press detection
        self.encoder.irq(
            trigger=Pin.IRQ_FALLING,
            handler=self._on_press,
            hard=True
        )

    def enter(self):
        _, _, _, _, h, m, _, _ = self.rtc.datetime()
        self.new_hour = h
        self.new_minute = m
        self.stage = 0
        self.setting = True
        self.last_edge = ticks_ms()
        self._display_clock()

    def _on_edge(self, pin):
        if not self.setting or pin != self.encoder:
            return
        self.last_edge = ticks_ms()
        if self.stage == 0:
            self.new_hour = (self.new_hour + 1) % 24
        else:
            self.new_minute = (self.new_minute + 1) % 60
        self._display_clock()

    def _on_press(self, pin):
        if not self.setting or pin.value() != 0:
            return
        # pressing during clock set exits directly
        self.setting = False
        self.oled.fill(0)
        self.oled.show()
        print(f"→ Clock set: {self.new_hour:02}:{self.new_minute:02}")

    def _check_timeout(self, t):
        if not self.setting:
            return
        if ticks_diff(ticks_ms(), self.last_edge) < self.timeout_ms:
            return
        if self.stage == 0:
            self.stage = 1
            self.last_edge = ticks_ms()
            self._display_clock()
        else:
            self.setting = False
            self.oled.fill(0)
            self.oled.show()
            print(f"→ Clock set: {self.new_hour:02}:{self.new_minute:02}")

    def _display_clock(self):
        self.oled.fill(0)
        if self.stage == 0:
            self.oled.text("Set Clock Hour:", 0, 0)
            self.oled.text(f"{self.new_hour:02}:00", 0, 10)
            print(f"→ Setting hour: {self.new_hour:02}")
        else:
            self.oled.text("Set Clock Minute:", 0, 0)
            self.oled.text(f":{self.new_minute:02}", 0, 10)
            print(f"→ Setting minute: {self.new_minute:02}")
        self.oled.show()


now=utime.ticks_ms()
diff=utime.ticks_diff(now, last_edge_ms)


"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    handle_json = JsonHandler()
    while True:
        handle_json.read_json()
        value_dict = handle_json.json_object

        '''User Code begins here'''
        idle = IdleMode(encoder_pins=encoder,button_pin=button)








        '''User Code ends here'''


        handle_json.write_json()
        sleep_ms(0) # Yield control to the web server to be added when reading or writing to the JSON file
        



def main():
    # --------------------------------------------------------------------------
    # Below given code should not be modified (except for the name of ssid and password). 
    # Create a network connection
    ssid = '007'       #Set access point name 
    password = '12345678'      #Set your access point password
    ap = WLAN(AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)            #activating

    while ap.active() == False:
        pass
    print('Connection is successful')
    print(ap.ifconfig())
    # --------------------------------------------------------------------------
    Worker = WebServer()
    start_new_thread(Worker.runner,()) 
    pico_runner()   
    
   
    
            





if __name__=="__main__":
    main()