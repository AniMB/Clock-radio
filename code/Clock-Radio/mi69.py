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
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        self.volume = value_dict.get("volume", 5)
        self.muted = bool(value_dict.get("mute", 0))

        encoder3A.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
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

    def handle_edge(self, pin): pass
    def handle_button(self, pin): pass
    def handle_timeout(self): pass
    def handle_refresh(self): pass

    # ——— Universal Volume Handlers ———
    def _on_vol_rotate(self, pin):
        """Handle encoder3 rotation: CW up, CCW down, auto-unmute."""
        if pin is not encoder3A:
            return
        a = encoder3A.value()
        b = encoder3B.value()
        if a == b:
            if self.volume < 15:
                self.volume += 1
        else:
            if self.volume > 0:
                self.volume -= 1
        self.muted = False
        self._show_volume()
        self._save_volume_state()

    def _on_vol_button(self, pin):
        """Toggle mute on encoder3 switch press."""
        if pin is not encoder3SW:
            return
        self.muted = not self.muted
        self._show_volume()
        self._save_volume_state()

    def _show_volume(self):
        """Draw a horizontal volume bar at the bottom of the display."""
        bar_h = 5
        y0 = oled.height() - bar_h
        oled.fill_rect(0, y0, oled.width(), bar_h, 0)
        fill_w = 0 if self.muted else int((self.volume / 15) * oled.width())
        oled.fill_rect(0, y0, fill_w, bar_h, 1)
        oled.rect(0, y0, oled.width(), bar_h, 1)
        oled.show()

    def _save_volume_state(self):
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        value_dict["volume"] = self.volume
        value_dict["mute"] = int(self.muted)
        handle_json.write_json()



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

        # Load use24Hour from JSON
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        self.is_24h = bool(value_dict.get("use24Hour", 1))

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
            # toggle 12h/24h format
            self.is_24h = not self.is_24h
            from config.resources import handle_json
            handle_json.read_json()
            value_dict = handle_json.json_object
            value_dict["use24Hour"] = int(self.is_24h)
            handle_json.write_json()
            self.show_time()
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
    """Alarm setter: hour/minute with inactivity or confirm; toggle on/off via button; rings grey noise; snooze/disable on press."""
    def __init__(self, encoder_pin):
        super().__init__([encoder_pin], button_pin=toggle_button, timeout_ms=3000)
        self.stage = 1
        self.hour = 0
        self.minute = 0
        self.setting = False
        self.enabled = False  # alarm armed
        self._alarm_ringing = False
        self._ring_timer = None
        self._snooze_timer = None
        self._noise_i2c = I2C(1, sda=Pin(4), scl=Pin(5), freq=100000)
        self._noise_radio = RDA5807M(self._noise_i2c)
        toggle_button.irq(trigger=Pin.IRQ_FALLING|Pin.IRQ_RISING,
                           handler=self._on_alarm_button,
                           hard=True)

        # Load snooze duration from JSON
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        self.snooze_minutes = value_dict.get("snooze", 5)

    def enter(self):
        _, _, _, _, h, m, _, _ = rtc.datetime()
        self.hour, self.minute, self.stage, self.setting = h, m, 1, True
        self.last_edge = ticks_ms()
        self._display()

    def handle_edge(self, pin):
        if not self.setting or pin != self.encoder_pins[0]:
            return
        if self.stage == 1:
            self.hour = (self.hour + 1) % 24
        else:
            self.minute = (self.minute + 1) % 60
        self.last_edge = ticks_ms()
        self._display()

    def _on_alarm_button(self, pin):
        now = ticks_ms()
        if pin.value() == 0:
            self._press_time = now
            return
        duration = ticks_diff(now, getattr(self, '_press_time', now))
        if self._alarm_ringing:
            self._stop_ring()
            if duration >= self.timeout_ms:
                self.enabled = False
            self._snooze()
        elif not self.setting:
            self.enabled = not self.enabled
            self._show_status()
        else:
            self.handle_button_during_setting()

    def handle_button_during_setting(self):
        if self.stage == 1:
            self.stage = 2
            self.last_edge = ticks_ms()
            self._display()
        else:
            self._finalize()

    def handle_timeout(self):
        if self.setting:
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
        self._draw_status()

    def _finalize(self):
        self.setting = False
        oled.fill(0)
        oled.show()
        print(f"Alarm set: {self.hour:02}:{self.minute:02}")

        # Update JSON dictionary with new alarm time
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        value_dict["alarm_hour"] = self.hour
        value_dict["alarm_minute"] = self.minute
        value_dict["alarm_ampm"] = 0  # assuming 24-hour for now
        handle_json.write_json()

        if self.enabled:
            self.start_ring()
        else:
            idle.handle_timeout()

    def start_ring(self):
        if self._alarm_ringing:
            return
        self._alarm_ringing = True
        self._ring_timer = Timer(-1)
        self._ring_timer.init(period=200, mode=Timer.PERIODIC,
                              callback=lambda t: self._ring_noise())

    def _ring_noise(self):
        bits = getrandbits(8)
        freq = 88.0 + (bits / 255) * 20.0
        self._noise_radio.set_frequency(freq)

    def _stop_ring(self):
        if self._ring_timer:
            self._ring_timer.deinit()
        self._alarm_ringing = False
        oled.fill(0)
        oled.show()
        idle.handle_timeout()

    def _snooze(self):
        if self._snooze_timer:
            self._snooze_timer.deinit()
        self._snooze_timer = Timer(-1)
        self._snooze_timer.init(period=self.snooze_minutes * 60 * 1000,
                                 mode=Timer.ONE_SHOT,
                                 callback=lambda t: self.start_ring())

    def _show_status(self):
        st = "ALM ON" if self.enabled else "ALM OFF"
        w, h = oled.width(), oled.height()
        oled.fill_rect(w - 60, h - 10, 60, 10, 0)
        oled.text(st, w - len(st) * 8, h - 10)
        oled.show()

    def _draw_status(self):
        st = "ON" if self.enabled else "OFF"
        w, h = oled.width(), oled.height()
        oled.text(st, w - 20, h - 10)
        oled.show()

    def __repr__(self):
        return f"<AlarmMode(h={self.hour},m={self.minute},en={self.enabled},ringing={self._alarm_ringing})>"



# ——— Clock Mode ———
class ClockMode(ModeBase):
    """Clock setter: spin B for hour, button B to enter minute stage; inactivity confirms and returns to idle."""
    def __init__(self, encoder_pin):
        super().__init__([encoder_pin], button_pin=encoder_pin, timeout_ms=3000)
        self.stage = 1      # 1 = hour, 2 = minute
        self.hour = 0
        self.minute = 0
        self.setting = False

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
        # only active while setting and for encoder B
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
        # button press advances to minute stage if in hour
        if not self.setting or pin != self.button_pin:
            return
        if self.stage == 1:
            # go to minute selection
            self.stage = 2
            self.last_edge = ticks_ms()
            self._display()
        else:
            # manual confirm minute
            self._finalize()

    def handle_timeout(self):
        # inactivity confirms and exits
        if not self.setting:
            return
        self._finalize()

    def _display(self):
        oled.fill(0)
        if self.stage == 1:
            oled.text("Set Clock Hour:", 0, 0)
            oled.text(f"{self.hour:02}:00",     0, 10)
        else:
            oled.text("Set Clock Min :", 0, 0)
            oled.text(f":{self.minute:02}",    0, 10)
        oled.show()

    def _finalize(self):
        # finalize and return to idle
        self.setting = False
        oled.fill(0)
        oled.show()
        # set RTC if desired, else just log
        print(f"Clock set: {self.hour:02}:{self.minute:02}")
        idle.handle_timeout()

    def __repr__(self):
        return f"<ClockMode(hour={self.hour}, minute={self.minute})>"

# ——— FM Mode ———
class FMMode(ModeBase):
    """FM tuner: play frequency based on nowplaying index in web_data.json; exit on shared button or timeout."""
    def __init__(self, encoder_pin, button_pin):
        super().__init__([encoder_pin], button_pin=button_pin, timeout_ms=3000)
        self.freq = 101.9  # default
        self.setting = True

        # Load frequency from JSON using nowplaying
        from config.resources import handle_json
        handle_json.read_json()
        value_dict = handle_json.json_object
        nowplaying = value_dict.get("nowplaying", 1)
        self.freq = value_dict.get(f"freq{nowplaying}", 101.9)

        # initialize RDA5807M tuner
        self.i2c = I2C(1, sda=Pin(4), scl=Pin(5), freq=100000)
        self.radio = RDA5807M(self.i2c)
        self.radio.set_frequency(self.freq)
        self._show()

    def enter(self):
        self.setting = True
        self.last_edge = ticks_ms()
        self._show()

    def handle_edge(self, pin):
        # ignore rotary in FM mode
        pass

    def handle_button(self, pin):
        if pin == self.button_pin and self.setting:
            self.setting = False
            oled.fill(0); oled.show()
            idle.handle_timeout()

    def handle_timeout(self):
        if self.setting:
            self.setting = False
            oled.fill(0); oled.show()
            idle.handle_timeout()

    def _show(self):
        oled.fill(0)
        oled.text("FM Mode",       0,  0)
        oled.text(f"{self.freq:.1f} MHz", 0, 10)
        oled.show()

    def __repr__(self):
        _, _, _, _, h, m, s, _ = rtc.datetime()
        oled.fill(0)
        oled.text(f"Time: {h:02}:{m:02}:{s:02}", 0,  0)
        oled.text(f"Freq: {self.freq:.1f} MHz", 0, 10)
        oled.show()
        return f"<FMMode(time={h:02}:{m:02}:{s:02}, freq={self.freq:.1f}MHz)>"


idle=IdleMode(encoder_pins=[encoder2SW,encoder1A,encoder1B],button_pin=button)
alarm_mode = AlarmMode(encoder_pins=[encoder2SW,encoder1A,encoder1B],button_pin=button)
clock_mode = ClockMode(encoder_pin=[encoder2A,encoder2B,encoder4SW],button_pin=button)
fm_mode = FMMode(button_pin=button)




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