import json
import os
import sys
import framebuf

from machine import *
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer
from config.resources import _lock, json_obj
from network import WLAN, AP_IF
from libraries.ssd1306 import SSD1306_SPI



# Define columns and rows of the oled display. These numbers are the standard values. 
SCREEN_WIDTH = 128 #number of columns
SCREEN_HEIGHT = 64 #number of rows


# Initialize I/O pins associated with the oled display SPI interface

spi_sck = Pin(18) # sck stands for serial clock; always be connected to SPI SCK pin of the Pico
spi_sda = Pin(19) # sda stands for serial data;  always be connected to SPI TX pin of the Pico; this is the MOSI
spi_res = Pin(21) # res stands for reset; to be connected to a free GPIO pin
spi_dc  = Pin(20) # dc stands for data/command; to be connected to a free GPIO pin
spi_cs  = Pin(17) # chip select; to be connected to the SPI chip select of the Pico 

#
# SPI Device ID can be 0 or 1. It must match the wiring. 
#
SPI_DEVICE = 0 # Because the peripheral is connected to SPI 0 hardware lines of the Pico

#
# initialize the SPI interface for the OLED display
#
oled_spi = SPI( SPI_DEVICE, baudrate= 100000, sck= spi_sck, mosi= spi_sda )

#
# Initialize the display
#
oled = SSD1306_SPI( SCREEN_WIDTH, SCREEN_HEIGHT, oled_spi, spi_dc, spi_res, spi_cs, True )


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
    
    while True:
        # Only read JSON when needed, not every loop
        handle_json.read_json()  # Read the JSON data into value_dict
        value_dict = handle_json.json_object
        

        '''User Code begins here'''

        # Example of how to use the value_dict
        
        # Simulate some processing or handling of the data
        # Update time in the JSON object
        
        
        

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