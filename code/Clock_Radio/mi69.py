import json
import os
import sys
from machine import Pin
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer

from config.resources import _lock
from network import WLAN, AP_IF




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
                    with open(self.__filename, 'r') as file:
                        
                        self.json_object= json.load(file)  
                    
                    
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
                with open(self.__filename, 'w') as file:
                    json.dump(self.json_object, file)
                
                return True
            except Exception as e:
                print(f"Error writing to {self.__filename}: {e}")
                return False
            finally:
                _lock.release()
            
        else:
            print("Lock is already acquired, cannot write JSON file.")

            return False  



"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    handle_json = JsonHandler()
    # Initialize JSON file if it doesn't exist
    if not handle_json.read_json():
        handle_json.write_json()
    
    while True:
        # Only read JSON when needed, not every loop
        value_dict = handle_json.json_object

        '''User Code begins here'''








        '''User Code ends here'''

        # Only write JSON if changes were made
        # handle_json.write_json()  # Comment out for now - write only when needed
        sleep_ms(100) # Yield control to the web server with reasonable delay
        



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