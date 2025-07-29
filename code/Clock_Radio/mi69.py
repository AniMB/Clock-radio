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
from libraries.display import oled
from libraries.radio import Radio



    

rtc=RTC()




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



button=Pin(0, Pin.IN, Pin.PULL_UP)


handle_json = JsonHandler()
handle_json.read_json()
value_dict = handle_json.json_object

# Initial setup
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

def alarm(value_dict):
    timestr = value_dict["Time"].strip()

    # Parse time string safely
    h, m, _ = map(int, timestr.split(":"))

    alarm_h=value_dict["alarm_hour"]
    alarm_m=value_dict["alarm_minute"]
    alarm_ampm=value_dict["alarm_ampm"]

    if value_dict["use24Hour"]:
        if alarm_h==h and alarm_m==m:
            return True
        else: return False
    else:
        alarm_h = alarm_h + 12 if value_dict["time_ampm"] == "PM" else alarm_h
        if alarm_h==h and alarm_m==m:
            return True
        



def _show_volume(vol, mute):
        """Draw a horizontal volume bar at the bottom of the display."""
        bar_h = 5
        y0 = oled.height() - bar_h
        oled.fill_rect(0, y0, oled.width(), bar_h, 0)
        fill_w = 0 if mute else int((vol/ 15) * oled.width())
        oled.fill_rect(0, y0, fill_w, bar_h, 1)
        oled.rect(0, y0, oled.width(), bar_h, 1)

"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    
    # Initialize JSON file if it doesn't exist
    if not handle_json.read_json():
        handle_json.write_json()
    
    

    while True:
        handle_json.read_json()
        value_dict = handle_json.json_object
        
        
        if alarm(value_dict):
            fm_radio.SetFrequency(100.1)
            fm_radio.SetVolume(100)
            fm_radio.ProgramRadio()



        time_str, ampm = increment_and_update_time(value_dict)
        draw_clock(time_str, ampm)
        

        if value_dict.get("radioflag", 1):
            fm_radio.ProgramRadio()
            idx = max(1, min(3, int(value_dict.get("nowplaying", 1))))
            freq = float(value_dict.get(f"freq{idx}", 100.0))
            oled.fill_rect(0, 10, oled.width(), 10, 0)
            oled.text("Now:", 0, 10)
            oled.text("{:.1f}MHz".format(freq), 40, 10)
        else:
            oled.fill_rect(0, 10, oled.width(), 10, 0)



        _show_volume(value_dict["volume"], value_dict["mute"])

        

        
        
        oled.show()

        

        






        '''User Code ends here'''

        # Only write JSON if changes were made
        handle_json.write_json()  
        sleep_ms(1) # Yield control to the web server with reasonable delay
        



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