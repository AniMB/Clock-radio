from machine import Pin
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer


"""Make a read json write json function that uses a lock to ensure thread safety. This will be for the main.py file."""




"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""

def main():

    Worker = WebServer()
    start_new_thread(Worker.runner,())





    
    
    sleep_ms(0) # Yield control to the web server to be added when reading or writing to the JSON file
    
            





if __name__=="__main__":
    main()