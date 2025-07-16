from machine import Pin
from utime import *
from threading import Thread
from resources import *
from web import Website







"""The main needs to have a time.sleep(0). This is to yield control to the web server.
This is because the web server runs in a while loop and needs to be able to process requests"""

def main():

    WebServer = Website("data.json", "webpage.html")
    web_thread = Thread(target=WebServer.runner, daemon=True)
    time.sleep(0) # Yield control to the web server
    pass
    
            





if __name__=="__main__":
    main()