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
encoder4SW,encoder2A,encoder2B,
encoder3SW,encoder3A,encoder3B]


button=Pin(0, Pin.IN, Pin.PULL_UP)


#define display pins
spi_sck = Pin(18)
spi_sda = Pin(19)
spi_res = Pin(21)
spi_dc  = Pin(20)
spi_cs  = Pin(17)



# ——— Hardware Initialization ———
rtc = RTC()
spi = SPI(0, sck=Pin(18), mosi=Pin(19), baudrate=100000)
oled = SSD1306_SPI(128, 64, spi, dc=Pin(20), res=Pin(21), cs=Pin(17), reset=True)



class ModeBase:
    """
    Base class for all modes: handles encoder IRQs, button IRQs,
    inactivity timeout, and optional refresh timer.
    Subclasses override handle_edge, handle_button, handle_timeout, handle_refresh.
    """
    def __init__(
        self,
        encoder_pins,
        button_pin=None,
        timeout_ms=3000,
        refresh_ms=None
    ):
        self.encoder_pins = encoder_pins
        self.button_pin = button_pin
        self.timeout_ms = timeout_ms
        self.last_edge = ticks_ms()
        # attach encoder interrupts
        for enc in self.encoder_pins:
            enc.irq(trigger=Pin.IRQ_RISING|Pin.IRQ_FALLING,
                    handler=self._on_edge,
                    hard=True)
        # attach button if provided
        if self.button_pin:
            self.button_pin.irq(trigger=Pin.IRQ_FALLING,
                                handler=self._on_button,
                                hard=True)
        # inactivity timer
        self._timer = Timer(-1)
        self._timer.init(period=self.timeout_ms,
                         mode=Timer.PERIODIC,
                         callback=self._on_timeout)
        # optional refresh timer
        if refresh_ms:
            self._refresh = Timer(-1)
            self._refresh.init(period=refresh_ms,
                               mode=Timer.PERIODIC,
                               callback=self._on_refresh)

    def _on_edge(self, pin):
        self.last_edge = ticks_ms()
        self.handle_edge(pin)

    def _on_button(self, pin):
        self.last_edge = ticks_ms()
        self.handle_button(pin)

    def _on_timeout(self, t):
        if ticks_diff(ticks_ms(), self.last_edge) >= self.timeout_ms:
            self.handle_timeout()

    def _on_refresh(self, t):
        self.handle_refresh()

    # Methods to override in subclasses:
    def handle_edge(self, pin):
        pass
    def handle_button(self, pin):
        pass
    def handle_timeout(self):
        pass
    def handle_refresh(self):
        pass


# ——— Idle Mode ———
class IdleMode(ModeBase):
    def __init__(self, encoder_pins, button_pin):
        self.current_mode = 1
        self.is_24h = True
        super().__init__(encoder_pins, button_pin, timeout_ms=3000, refresh_ms=1000)

    def handle_edge(self, pin):
        # exit idle and clear display
        self.oled.fill(0); self.oled.show()
        if pin == self.encoder_pins[0]:
            self.current_mode = (self.current_mode % 3) + 1
            self.show_mode_menu()
            if pin == self.encoder_pins[0]:
                alarm_mode.enter()
            elif pin == self.encoder_pins[3]:
                clock_mode.enter()
            elif pin == self.encoder_pins[7]:
                fm_mode.enter()



    def handle_button(self, pin):
        # toggle 12/24h format when idle; otherwise cycle mode
        if self.idle:
            self.is_24h = not self.is_24h
            self.show_time()
        else:
            self.current_mode = (self.current_mode % 3) + 1
            self.show_mode_menu()

    def handle_timeout(self):
        # enter idle: show time
        self.show_time()

    def handle_refresh(self):
        # refresh clock display
        self.show_time()

    def show_time(self):
        _, _, _, _, h, m, s, _ = rtc.datetime()
        if self.is_24h:
            ts = f"{h:02}:{m:02}:{s:02}"
        else:
            suffix = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            ts = f"{h12:02}:{m:02}:{s:02} {suffix}"
        oled.fill(0)
        oled.text(ts, 0, 0)
        oled.show()

    def show_mode_menu(self):
        """Display mode menu and dispatch based on selection: 1=Clock, 2=Alarm, 3=FM."""
        oled.fill(0)
        oled.text("Which Mode?", 0, 0)
        oled.text("1=Clk 2=Alm 3=FM", 0, 10)
        oled.show()
        # dispatch to sub-modes
        if self.current_mode == 1:
            alarm_mode.enter()
        elif self.current_mode == 2:
            clock_mode.enter()
        elif self.current_mode == 3:
            fm_mode.enter()

    def __repr__(self):
        """If idle, display current time on the OLED; then return state repr."""
        # Side effect: update display if in idle mode
        if getattr(self, 'idle', False):
            self.show_time()
        # Return a concise internal-state snapshot
        return f"<IdleMode(mode={self.current_mode}, is_24h={self.is_24h})>"

# ——— Alarm Mode ———
class AlarmMode(ModeBase):
    def __init__(self, encoder_pin):
        self.stage=0; self.hour=0; self.minute=0; self.setting=False
        super().__init__([encoder_pin], timeout_ms=3000)

    def enter(self):
        _, _, _, _, h, m, _, _ = rtc.datetime()
        self.hour, self.minute, self.stage, self.setting = h, m, 0, True
        self.last_edge = ticks_ms()
        self.display()

    def handle_edge(self, pin):
        if not self.setting: return
        if self.stage==0:
            self.hour=(self.hour+1)%24
        else:
            self.minute=(self.minute+1)%60
        self.display()

    def handle_timeout(self):
        if self.stage==0:
            self.stage=1; self.last_edge=ticks_ms(); self.display()
        else:
            self.setting=False; oled.fill(0); oled.show(); print(f"Alarm set: {self.hour:02}:{self.minute:02}")

    def display(self):
        oled.fill(0)
        if self.stage==0:
            oled.text("Set Alarm Hour:",0,0); oled.text(f"{self.hour:02}:00",0,10)
        else:
            oled.text("Set Alarm Min:" ,0,0); oled.text(f":{self.minute:02}",0,10)
        oled.show()

    def __repr__(self):
        return f"<AlarmMode(stage={self.stage}, hour={self.hour}, min={self.minute})>"

# ——— Clock Mode ———
class ClockMode(ModeBase):
    def __init__(self, encoder_pin):
        self.stage=0; self.hour=0; self.minute=0; self.setting=False
        super().__init__([encoder_pin], timeout_ms=3000)

    def enter(self):
        _, _, _, _, h, m, _, _ = rtc.datetime()
        self.hour, self.minute, self.stage, self.setting = h, m, 0, True
        self.last_edge = ticks_ms()
        self.display()

    def handle_edge(self, pin):
        if not self.setting: return
        if self.stage==0:
            self.hour=(self.hour+1)%24
        else:
            self.minute=(self.minute+1)%60
        self.display()

    def handle_button(self, pin):
        if self.setting and pin.value()==0:
            self.setting=False; oled.fill(0); oled.show(); print(f"Clock set: {self.hour:02}:{self.minute:02}")

    def handle_timeout(self):
        if self.stage==0:
            self.stage=1; self.last_edge=ticks_ms(); self.display()
        else:
            self.setting=False; oled.fill(0); oled.show(); print(f"Clock set: {self.hour:02}:{self.minute:02}")

    def display(self):
        oled.fill(0)
        if self.stage==0:
            oled.text("Set Clock Hour:",0,0); oled.text(f"{self.hour:02}:00",0,10)
        else:
            oled.text("Set Clock Min:",0,0); oled.text(f":{self.minute:02}",0,10)
        oled.show()

    def __repr__(self):
        return f"<ClockMode(stage={self.stage}, hour={self.hour}, min={self.minute})>"

# ——— FM Mode ———
class FMMode(ModeBase):
    """FM mode: tune TEA5767, volume via encoder, display freq and time on repr."""
    def __init__(self, freq_enc_pin):
        # only frequency encoder used here
        self.freq = 101.9
        self.volume = 5
        # I2C for TEA5767
        self.i2c = I2C(1, sda=Pin(4), scl=Pin(5), freq=100000)
        self.radio = TEA5767(self.i2c)
        super().__init__([freq_enc_pin], timeout_ms=3000)

    def enter(self):
        self.setting = True
        self.last_edge = ticks_ms()
        self.radio.set_frequency(self.freq)
        oled.fill(0)
        oled.text("FM Mode", 0, 0)
        oled.text(f"{self.freq:.1f} MHz", 0,10)
        oled.text(f"Vol: {self.volume}", 0,20)
        oled.show()

    def handle_edge(self, pin):
        if pin != self.encoder_pins[0]:
            return
        self.last_edge = ticks_ms()
        # step frequency
        self.freq = round(self.freq + 0.1, 1)
        self.radio.set_frequency(self.freq)
        oled.fill(0)
        oled.text("FM Mode", 0, 0)
        oled.text(f"{self.freq:.1f} MHz", 0,10)
        oled.text(f"Vol: {self.volume}", 0,20)
        oled.show()

    def handle_button(self, pin):
        # exit FM
        if pin.value() == 0:
            self.setting = False
            oled.fill(0)
            oled.show()
            idle.handle_timeout()

    def handle_timeout(self):
        if getattr(self, 'setting', False):
            self.setting = False
            oled.fill(0)
            oled.show()
            idle.handle_timeout()

    def __repr__(self):
        # display time
        _, _, _, _, h, m, s, _ = rtc.datetime()
        oled.fill(0)
        oled.text(f"Time: {h:02}:{m:02}:{s:02}", 0, 0)
        oled.text(f"Freq: {self.freq:.1f}MHz", 0,10)
        oled.show()
        return f"<FMMode(time={h:02}:{m:02}:{s:02}, freq={self.freq:.1f}MHz)>"






"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    handle_json = JsonHandler()
    while True:
        handle_json.read_json()
        value_dict = handle_json.json_object

        '''User Code begins here'''








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