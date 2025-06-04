from machine import Pin
from utime import *
from basicdisplay import counter
def main():
    print("Hello world")
    count=0
    push=Pin(0, Pin.PULL_UP, Pin.IN)
    led=Pin('LED',Pin.OUT)
    state=0
    while True:
        led.value(1)
        if push.value()==0 and (state==0):
            led.value(0)
            count+=1
            state=1
            print(count)
        if push.value==1:
            state=0
        counter(count)    
            





if __name__=="__main__":
    main()