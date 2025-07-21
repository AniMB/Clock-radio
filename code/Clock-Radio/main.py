import json
import os
import sys
from machine import Pin
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer
from typing import Any
from config.resources import _lock



"""Make a read json write json function that uses a lock to ensure thread safety. This will be for the main.py file."""
class JsonHandler:
    def __init__(self):
        self.__filename = "database/web_data.json"
        self.__lock = _lock
        self.json_object = {}

    def read_json(self) ->bool:
        if self.__lock.acquire(blocking=False):

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
        else:
            print("Lock is already acquired, cannot read JSON file.")
            return False

    def write_json(self) -> bool:
        if self.__lock.acquire(blocking=False):

            try:
                with open(self.__filename, 'w') as file:
                    json.dump(self.json_object, file, indent=4)  # type: ignore
                return True
            except Exception as e:
                print(f"Error writing to {self.__filename}: {e}")
                return False
        else:
            print("Lock is already acquired, cannot write JSON file.")
            return False  



"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""
def pico_runner():
    handle_json = JsonHandler()
    handle_json.read_json()
    value_dict = handle_json.json_object

    '''User Code begins here'''








    '''User Code ends here'''


    handle_json.write_json()



def main():
    pico_runner()
    Worker = WebServer()
    start_new_thread(Worker.runner,())    
    
    sleep_ms(0) # Yield control to the web server to be added when reading or writing to the JSON file
    
            





if __name__=="__main__":
    main()