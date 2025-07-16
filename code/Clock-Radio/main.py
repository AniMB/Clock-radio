from machine import Pin
from utime import *
from threading import Thread
from config.resources import *
from web_connectivity.web import WebServer







"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""

def main():

    Worker = WebServer()
    web_thread = Thread(target=Worker.runner, daemon=True)
    web_thread.start()
    
    
    sleep_ms(0) # Yield control to the web server to be added when reading or writing to the JSON file
    
            





if __name__=="__main__":
    main()