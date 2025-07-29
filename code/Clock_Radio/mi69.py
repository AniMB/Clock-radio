import json
import os
import sys
import framebuf
import time

from machine import *
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer
from config.resources import _lock
from network import WLAN, AP_IF
from libraries.display import *
from libraries.radio import Radio



    

rtc=RTC()

BUTTON_HOLD_MS = 3000       # 3 seconds = stop alarm
_DEBOUNCE_MS    = 60

_btn_down_ms      = None    # press start timestamp
_btn_short_req    = False   # set by IRQ, consumed in loop
_btn_long_req     = False   # set by IRQ, consumed in loop



"""Make a read json write json function that uses a lock to ensure thread safety. This will be for the main.py file."""
class JsonHandler:
    def __init__(self):
        self.__filename = "web_data.json"
      
        self.json_object = {
                    "alarm_hour": 0,
                    "alarm_minute": 0,
                    "alarm_ampm": 0,
                    "freq1": 101.9,
                    "freq2": 101.9,
                    "freq3": 101.9,
                    "volume": 50,
                    "nowplaying": 1,
                    "use24Hour": 1,
                    "mute": 0,
                    "Time": "12:00:00",
                    "time_ampm": 0,
                    "snooze": 5,
                    "cancelAlarm": 0
                    }

    def read_json(self) ->bool:
              

            if _lock.acquire():
                
                try:
                    with open(self.__filename, "r") as file:  
                        data = json.load(file)
                    self.json_object.clear()  # Clear the current json_object
                    self.json_object.update(data)                
                    return True
                except Exception as e:
                    print(f"Error reading from {self.__filename}: {e}")
                    return False
                finally:
                    _lock.release()
            else:
                print("Lock is already acquired, cannot read JSON file.")
                return False
       
    def write_json(self) -> bool:
        if _lock.acquire():
           
            try:
                with open(self.__filename, "w") as file:
                    json.dump(self.json_object, file)
                print(f"JSON data written to {self.__filename} successfully.")
                
                return True
            except Exception as e:
                print(f"Error writing to {self.__filename}: {e}")
                return False
            finally:
                _lock.release()
            
        else:
            print("Lock is already acquired, cannot write JSON file.")

            return False  




#helper function to increase the current time in a specific format
def increment_and_update_time(value_dict):
    try:
        timestr = value_dict["Time"].strip()

        # Parse time string safely
        h, m, s = map(int, timestr.split(":"))

        # Increment by 1 second
        s += 1
        if s >= 60:
            s = 0
            m += 1
            if m >= 60:
                m = 0
                h += 1
                if h >= 24:
                    h = 0
        value_dict["Time"] = f"{h:02}:{m:02}:{s:02}"
        # Format time
        ampm = ""
        if value_dict.get("use24Hour", 1) == 0:
            ampm = "AM" if h < 12 else "PM"
            if h == 0:
                h = 12
            elif h > 12:
                h -= 12
        time_str = f"{h:02}:{m:02}:{s:02}"
        # Format and update the dictionary
       
        return time_str, ampm
    except Exception as e:
        print(f"Error incrementing time: {e}")
        return value_dict["Time"], ""




# Initial setup

button=Pin(0, Pin.IN, Pin.PULL_UP)


handle_json = JsonHandler()
handle_json.read_json()
value_dict = handle_json.json_object


fm_radio = Radio(
    value_dict[f"freq{value_dict['nowplaying']}"],
    value_dict["volume"],
    value_dict["mute"]
)

def draw_clock(time_str, ampm):
    """
    Draw only when the content changes to avoid OLED flicker and CPU waste.
    """
    global _last_drawn
    stamp = (time_str, ampm)
    if stamp == _last_drawn:
        return
    _last_drawn = stamp
    global _update_tick_due
    _update_tick_due=False
    oled.fill(0)
    oled.text(time_str, 0, 0)
    if ampm:
        oled.text(ampm, 80, 0)  # adjust x if your screen width differs
    

_update_tick_due = False
_last_drawn = None  # cache last string shown to avoid redundant OLED work

def on_timeout(t):            # MUST accept the timer arg
    # IRQ-safe
    global _update_tick_due
    _update_tick_due = True

timer = Timer(-1)
timer.init(period=1000, mode=Timer.PERIODIC, callback=on_timeout)


_snoozeflag=False
_alarmflag=False
_Radioflag=False

def _button_irq(pin):
    global _btn_down_ms, _btn_short_req, _btn_long_req
    now = ticks_ms()
    if pin.value() == 0:  # pressed (falling)
        # debounce press start
        if _btn_down_ms is None:
            _btn_down_ms = now
    else:  # released (rising)
        if _btn_down_ms is not None:
            dur = ticks_diff(now, _btn_down_ms)
            _btn_down_ms = None
            if dur >= BUTTON_HOLD_MS:
                _btn_long_req = True
            elif dur >= _DEBOUNCE_MS:
                _btn_short_req = True

# Attach to your existing button pin
button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_button_irq, hard=True)



class Alarm:
    alarm_h=0
    alarm_m=0

    def __init__(self): pass

    


    @staticmethod
    def to_24h(hour: int, minute: int, am_pm: str) -> tuple[int, int]:
        """
        Convert 12-hour (hour, minute, am_pm) to 24-hour (h24, m).

        Parameters
        ----------
        hour : int
            1..12 inclusive
        minute : int
            0..59 inclusive
        am_pm : str
            "AM" or "PM" (case-insensitive)

        Returns
        -------
        (h24, m) : tuple[int, int]
            h24 in 0..23, m in 0..59

        Raises
        ------
        ValueError if inputs are invalid.
        """
        if not isinstance(am_pm, str):
            raise ValueError("am_pm must be a string 'AM' or 'PM'.")

        tag = am_pm.strip().upper()
        if tag not in ("AM", "PM"):
            raise ValueError("am_pm must be 'AM' or 'PM' (case-insensitive).")

        if not (1 <= int(hour) <= 12):
            raise ValueError("hour must be in 1..12 for 12-hour input.")
        if not (0 <= int(minute) <= 59):
            raise ValueError("minute must be in 0..59.")

        h = int(hour)
        m = int(minute)

        if tag == "AM":
            h24 = 0 if h == 12 else h
        else:  # "PM"
            h24 = 12 if h == 12 else h + 12

        return h24, m



    def sync_from_dict(self,value_dict):
        
        self.snooze_minutes = value_dict.get("snooze", 5)
        self.alarm_hour = value_dict.get("alarm_hour", 0)
        self.alarm_minute = value_dict.get("alarm_minute", 0)
        self.alarm_ampm=value_dict.get("alarm_ampm","AM")
        self.alarm_enabled = not bool(value_dict.get("cancelAlarm", 0))  # ← Add this line

        if not value_dict["use24Hour"]:
            self.alarm_hour,self.alarm_minute=self.to_24h(self.alarm_hour,self.alarm_minute,self.alarm_ampm)

        Alarm.alarm_h=self.alarm_hour
        Alarm.alarm_m=self.alarm_minute


    


    def is_alarm(self,value_dict):
        if not self.alarm_enabled :
            return False

        timestr = value_dict["Time"].strip()

        # Parse time string safely
        h, m, _= map(int, timestr.split(":"))
        # self.alarm_hour/minute are already in 24h from sync_from_dict()
        return (self.alarm_hour == h) and (self.alarm_minute == m)
        
    def on_snooze(self):
        global _snoozeflag, _alarmflag
        
        _alarmflag,_snoozeflag=True, True
        
        
        self.alarm_minute=Alarm.alarm_m+self.snooze_minutes
        if self.alarm_minute>=60:
            self.alarm_hour=(self.alarm_hour+1)%24
        try:
            fm_radio.SetMute(True)
            fm_radio.ProgramRadio()
        except Exception:
            pass
    
    
    def stop_alarm(self):
        global _snoozeflag, _alarmflag
        _snoozeflag=False
        _alarmflag=False
        try:
            fm_radio.SetMute(True)
            fm_radio.ProgramRadio()
        except Exception:
            pass
       
alarm=Alarm()
def on_stop():
    global alarm
    alarm.stop_alarm()
    # No need to delete; just reassign
    alarm = Alarm()



def _show_volume(vol, mute):
        """Draw a horizontal volume bar at the bottom of the display."""
        
        bar_h = 5
        y0 = SCREEN_HEIGHT - bar_h
        oled.fill_rect(0, y0, SCREEN_WIDTH , bar_h, 0)

        # assume vol is 0..100; clamp
        try:
            vol = int(vol)
        except Exception:
            vol = 0
        if vol < 0: vol = 0
        if vol > 100: vol = 100

        fill_w = 0 if mute else int((vol / 100.0) * SCREEN_WIDTH )
        oled.fill_rect(0, y0, fill_w, bar_h, 1)
        oled.rect(0, y0, SCREEN_WIDTH , bar_h, 1)


"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    global _snoozeflag, _Radioflag, _alarmflag

    # Initialize JSON file if it doesn't exist
    if not handle_json.read_json():
        handle_json.write_json()
    
    handle_json.read_json()
    value_dict = handle_json.json_object
    value_dict[""]

    while True:
        handle_json.read_json()
        value_dict = handle_json.json_object
        
        global _btn_short_req, _btn_long_req
        if _btn_long_req and _alarmflag:
            _btn_long_req = False
            on_stop()  # long press >= 3s -> stop alarm
        elif _btn_short_req and _alarmflag:
            _btn_short_req = False
            alarm.on_snooze()    # short press -> snooze
        elif _btn_short_req and _Radioflag:
            _btn_short_req = False
            _Radioflag=False
        elif _btn_short_req and not _Radioflag:
            _btn_short_req = False
            _Radioflag=True




        
        if not _snoozeflag:
            alarm.sync_from_dict(value_dict)

        
        if alarm.is_alarm(value_dict):
            _alarmflag=True
            _Radioflag=False
            fm_radio.SetFrequency(100.1)
            fm_radio.SetVolume(100)
            fm_radio.ProgramRadio()



        global _update_tick_due
        if _update_tick_due:
            _update_tick_due = False
            time_str, ampm = increment_and_update_time(value_dict)
            draw_clock(time_str, ampm)

        if _Radioflag and not _alarmflag:
            idx = max(1, min(3, int(value_dict.get("nowplaying", 1))))
            freq = float(value_dict.get(f"freq{idx}", 100.0))
            if (fm_radio.GetSettings()[0:3]!=(not value_dict["mute"], value_dict["volume"],freq)):
                fm_radio.SetMute(value_dict["mute"])
                fm_radio.SetVolume(value_dict["volume"])
                fm_radio.SetFrequency(freq)
                fm_radio.ProgramRadio()
            
            oled.fill_rect(0, 10, SCREEN_WIDTH , 10, 0)
            oled.text("Now:", 0, 10)
            oled.text("{:.1f}MHz".format(freq), 40, 10)
        else:
            _Radioflag=False
            oled.fill_rect(0, 10, SCREEN_WIDTH , 10, 0)



        _show_volume(value_dict["volume"], value_dict["mute"])

        

        
        
        oled.show()

        

        






        '''User Code ends here'''

        # Only write JSON if changes were made
        handle_json.write_json()  
        sleep_ms(1000) # Yield control to the web server with reasonable delay
        



def main():
    # --------------------------------------------------------------------------
    # Below given code should not be modified (except for the name of ssid and password). 
    # Create a network connection
    ssid = '007'       #Set access point name 
    password = '212173314'      #Set your access point password
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