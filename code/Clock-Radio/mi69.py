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





# ——— Hardware Initialization ———
rtc = RTC()
spi = SPI(0, sck=Pin(18), mosi=Pin(19), baudrate=100000)
oled = SSD1306_SPI(128, 64, spi, dc=Pin(20), res=Pin(21), cs=Pin(17), reset=True)



class ModeBase:
    """
    Handles encoder/button IRQs and a 3s inactivity watchdog.
    Subclasses override handle_edge, handle_button, handle_timeout, handle_refresh.
    """
    def __init__(self, encoder_pins, button_pin=None, timeout_ms=3000):
        self.encoder_pins = encoder_pins
        self.button_pin = button_pin
        self.timeout_ms = timeout_ms
        self.last_edge = ticks_ms()
        for enc in self.encoder_pins:
            enc.irq(trigger=Pin.IRQ_RISING|Pin.IRQ_FALLING,
                    handler=self._on_edge, hard=True)
        if self.button_pin:
            self.button_pin.irq(trigger=Pin.IRQ_FALLING,
                                handler=self._on_button, hard=True)
        self._timer = Timer(-1)
        self._timer.init(period=self.timeout_ms,
                         mode=Timer.PERIODIC,
                         callback=self._on_timeout)
        # universal volume controls
        self.volume = 5
        self.muted = False
        encoder3A.irq(trigger=Pin.IRQ_RISING|Pin.IRQ_FALLING,
                      handler=self._on_vol_rotate, hard=True)
        encoder3SW.irq(trigger=Pin.IRQ_FALLING,
                       handler=self._on_vol_button, hard=True)

    def _on_edge(self, pin):
        self.last_edge = ticks_ms(); self.handle_edge(pin)
    def _on_button(self, pin):
        self.last_edge = ticks_ms(); self.handle_button(pin)
    def _on_timeout(self, t):
        if ticks_diff(ticks_ms(), self.last_edge) >= self.timeout_ms:
            self.handle_timeout()
    def handle_edge(self, pin):       pass
    def handle_button(self, pin):     pass
    def handle_timeout(self):         pass
    def handle_refresh(self):         pass

    # ——— Universal Volume Handlers ———
    def _on_vol_rotate(self, pin):
        """Handle encoder3 rotation: CW up, CCW down, auto-unmute."""
        # only act on encoder3A edges
        if pin is not encoder3A:
            return
        a = encoder3A.value()
        b = encoder3B.value()
        # direction: CW if A==B
        if a == b:
            if self.volume < 15:
                self.volume += 1
        else:
            if self.volume > 0:
                self.volume -= 1
        self.muted = False
        self._show_volume()

    def _on_vol_button(self, pin):
        """Toggle mute on encoder3 switch press."""
        if pin is not encoder3SW:
            return
        self.muted = not self.muted
        self._show_volume()

    def _show_volume(self):
        """Draw a horizontal volume bar at the bottom of the display."""
        # clear only bottom bar area
        bar_h = 5
        y0 = oled.height() - bar_h
        oled.fill_rect(0, y0, oled.width(), bar_h, 0)
        # compute fill width
        fill_w = 0 if self.muted else int((self.volume / 15) * oled.width())
        # filled portion
        oled.fill_rect(0, y0, fill_w, bar_h, 1)
        # outline full bar
        oled.rect(0, y0, oled.width(), bar_h, 1)
        oled.show()


# ——— Idle Mode ———
class IdleMode(ModeBase):
    """
    Clock display, 12/24 toggle, mode-select menu via encoder A,
    blinking arrow, and direct FM entry via encoder C.
    """
    def __init__(self, encoder_pins, button_pin):
        super().__init__(encoder_pins, button_pin, timeout_ms=3000)
        self.current_mode = 1
        self.selecting_mode = False
        self._arrow_visible = True
        self.is_24h = True
        self.idle = False
        # refresh timer: blink arrow every 500ms and refresh clock in idle
        self._refresh = Timer(-1)
        self._refresh.init(period=500,
                           mode=Timer.PERIODIC,
                           callback=lambda t: self.handle_refresh())

    def handle_edge(self, pin):
        if self.selecting_mode and pin == self.encoder_pins[0]:
            # rotate to change selection
            self.current_mode = (self.current_mode % 3) + 1
            self._draw_menu()
        elif not self.selecting_mode and pin == self.encoder_pins[2]:
            # direct FM entry on encoder C
            fm_mode.enter()
        self.idle = False
        oled.fill(0); oled.show()

    def handle_button(self, pin):
        if pin != self.button_pin:
            return
        if not self.selecting_mode:
            # start mode selection
            self.selecting_mode = True
            self.current_mode = 1
            self._arrow_visible = True
            self._draw_menu()
        else:
            # confirm selection
            sel = self.current_mode
            self.selecting_mode = False
            oled.fill(0); oled.show()
            if sel == 1:
                alarm_mode.enter()
            elif sel == 2:
                clock_mode.enter()
            else:
                fm_mode.enter()

    def handle_timeout(self):
        if self.selecting_mode:
            # abort selection on timeout
            self.selecting_mode = False
            self.idle = True
            self.show_time()
        else:
            # enter idle clock
            self.idle = True
            self.show_time()

    def handle_refresh(self):
        if self.selecting_mode:
            # blink arrow
            self._arrow_visible = not self._arrow_visible
            self._draw_menu()
        elif self.idle:
            # refresh clock in idle
            self.show_time()

    def show_time(self):
        _,_,_,_,h,m,s,_ = rtc.datetime()
        if self.is_24h:
            ts = f"{h:02}:{m:02}:{s:02}"
        else:
            suffix = "AM" if h < 12 else "PM"
            hh = h % 12 or 12
            ts = f"{hh:02}:{m:02}:{s:02} {suffix}"
        oled.fill(0)
        oled.text(ts, 0, 0)
        oled.show()
        self.selecting_mode = False

    def _draw_menu(self):
        oled.fill(0)
        oled.text("Which Mode?", 0, 0)
        oled.text("1=Alarm",    0, 10)
        oled.text("2=Clock",    0, 20)
        oled.text("3=FM",       0, 30)
        if self._arrow_visible:
            y = self.current_mode * 10
            oled.text(">", 60, y)
        oled.show()

    def __repr__(self):
        if self.idle:
            self.show_time()
        fmt = '24h' if self.is_24h else '12h'
        return f"<IdleMode(mode={self.current_mode}, format={fmt})>"

# ——— Alarm Mode ———
class AlarmMode(ModeBase):
    """Alarm setter: spin A for hour, button A to enter minute stage, inactivity confirms setting; button toggles alarm on/off."""
    def __init__(self, encoder_pin):
        super().__init__([encoder_pin], timeout_ms=3000)
        self.stage = 1        # 1 = hour, 2 = minute
        self.hour = 0
        self.minute = 0
        self.setting = False
        self.enabled = False  # alarm on/off

    def enter(self):
        # load current time
        _, _, _, _, h, m, _, _ = rtc.datetime()
        self.hour = h
        self.minute = m
        self.stage = 1
        self.setting = True
        self.last_edge = ticks_ms()
        self._display()

    def handle_edge(self, pin):
        if not self.setting or pin != self.encoder_pins[0]:
            return
        # adjust hour or minute
        if self.stage == 1:
            self.hour = (self.hour + 1) % 24
        else:
            self.minute = (self.minute + 1) % 60
        self.last_edge = ticks_ms()
        self._display()

    def handle_button(self, pin):
        # toggle alarm on/off if not in setting
        if not self.setting and pin == self.button_pin:
            self.enabled = not self.enabled
            self._show_status()
            return
        # button A advances to minute stage or confirms
        if not self.setting or pin != self.button_pin:
            return
        if self.stage == 1:
            # move to minute selection
            self.stage = 2
            self.last_edge = ticks_ms()
            self._display()
        else:
            # manual confirm in minute stage
            self._finalize()

    def handle_timeout(self):
        # inactivity triggers finalize at any stage
        if not self.setting:
            return
        self._finalize()

    def _display(self):
        oled.fill(0)
        if self.stage == 1:
            oled.text("Set Alarm Hour:", 0, 0)
            oled.text(f"{self.hour:02}:00",     0, 10)
        else:
            oled.text("Set Alarm Min :", 0, 0)
            oled.text(f":{self.minute:02}",    0, 10)
        oled.show()
        # also show current on/off status
        self._draw_status()

    def _finalize(self):
        # finish setting and return to idle
        self.setting = False
        oled.fill(0)
        oled.show()
        # print for debugging
        print(f"Alarm set: {self.hour:02}:{self.minute:02}")
        idle.handle_timeout()

    def _show_status(self):
        # display alarm on/off at bottom-right
        bar_h = 10
        y0 = oled.height() - bar_h
        oled.fill_rect(oled.width() - 60, y0, 60, bar_h, 0)
        status = "ALM ON" if self.enabled else "ALM OFF"
        x = oled.width() - len(status) * 8
        oled.text(status, x, y0)
        oled.show()

    def _draw_status(self):
        # called during display to show status
        status = "ON" if self.enabled else "OFF"
        x = oled.width() - 20
        y = oled.height() - 10
        oled.text(status, x, y)
        oled.show()

    def __repr__(self):
        return f"<AlarmMode(hour={self.hour}, minute={self.minute}, enabled={self.enabled})>"(self):
        return f"<AlarmMode(hour={self.hour}, minute={self.minute})>"

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
        """Rotate encoder to step FM frequency, with out-of-range feedback."""
        if pin != self.encoder_pins[0]:
            return
        from utime import ticks_ms
        self.last_edge = ticks_ms()
        # compute next freq
        new_freq = round(self.freq + 0.1, 1)
        # check valid FM band
        if new_freq < 88.0 or new_freq > 108.0:
            oled.fill(0)
            oled.text("Invalid freq", 0, 0)
            oled.show()
            return
        self.freq = new_freq
        self.radio.set_frequency(self.freq)
        # update display
        oled.fill(0)
        oled.text("FM Mode", 0, 0)
        oled.text(f"{self.freq:.1f}MHz", 0, 10)
        oled.text(f"Vol: {self.volume}", 0, 20)
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
        idle=IdleMode(encoder_pins=encoder,button_pin=button)
        alarm_mode = AlarmMode(encoder1A)
        clock_mode = ClockMode(encoder2A)
        fm_mode    = FMMode(encoder3A)







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