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
        print(f"❌ Error incrementing time: {e}")
        return value_dict["Time"], ""


"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    handle_json = JsonHandler()
    # Initialize JSON file if it doesn't exist
    if not handle_json.read_json():
        handle_json.write_json()
    
    
    handle_json.read_json()
    value_dict = handle_json.json_object

    # Initial setup
    fm_radio = Radio(
        value_dict[f"freq{value_dict['nowplaying']}"],
        value_dict["volume"],
        value_dict["mute"]
    )

    while True:
        handle_json.read_json()
        value_dict = handle_json.json_object

        
            

        time, time_ampm=increment_and_update_time(value_dict)
        
        
        # Clear the buffer
        #
        oled.fill(0)
                
        #
        # Update the text on the screen
        oled.text(time, 0, 0, 1)
        oled.text(time_ampm, 100, 0, 1)  # Display AM/PM if using 12-hour format
        # Transfer the buffer to the screen
    
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