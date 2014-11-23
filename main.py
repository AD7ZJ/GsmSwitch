#!/usr/bin/env python
import serial,time,re   # Importing required modules
import RPi.GPIO as GPIO
import signal
import sys

#stup GPIO
switch1 = 26
switch2 = 23
GPIO.setmode(GPIO.BOARD)
GPIO.setup(switch1, GPIO.OUT)

#setup serial port to talk to SIM900
port = serial.Serial(baudrate=19200, port='/dev/ttyAMA0', timeout=5) # Serial port initialization
#port.open()
allow=["+919966228935","+919705896317"] # Add allowed Numbers here

# setup SIM900
port.write('AT+CMGF=1\r\n')              # set text mode
port.write('AT+CNMI=2,2,0,0,0\r\n')      # Output texts asynchronously
port.write('AT+CLTS=1\r\n')              # use network time to set internal clock

# catch ctrl-c so we can cleanup the GPIO driver
def sigHandler(signal, frame):
    print('Caught SIGINT, exiting...\n')
    GPIO.cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, sigHandler)

def WaitResponse(msg):
    startTime = time.time()
    resp = port.readline()
    while (resp.find(msg) < 0):
        print "Waiting... " + resp + "\r\n"
        if (time.time() - startTime > 8):
            print "timed out :(\r\n"
            break
        resp = port.readline()
    print "Got: " + resp


def SetSwitch1(state):
    if (state):
        GPIO.output(switch1, 1)
    else:
        GPIO.output(switch1, 0)


def SetSwitch2(state):
    if (state):
        GPIO.output(switch2, 1)
    else:
        GPIO.output(switch2, 0)


def SendSms(msg, phoneNumber="+19286427892"):
    port.write("AT+CMGS=\"%s\"\r\n" % phoneNumber)
    WaitResponse('>')
    port.write(msg)
    port.write('\x1A')
    WaitResponse('OK')

#def ProcessCmd(cmd):
    


while 1: # For Infinite execution
    line = port.readline() # Reading Serialport response line by line

    # a txt message will look like +CMT: "+19286427892","","14/11/19,00:37:33-28"
    if(line.startswith("+CMT:")): # Condition for new incoming message
        #                        number     ""      day   month  year   hour  min     sec
        m = re.search('\+CMT\: \"(\+\d+)\",(.*?),\"(\d+)\/(\d+)\/(\d+),(\d+)\:(\d+)\:(\d+).*', line)
        phoneNumber = m.group(1)

        day = int(m.group(5))
        month = int(m.group(4))
        year = int(m.group(3))
        hour = int(m.group(6))
        minute = int(m.group(7))
        sec = int(m.group(8))


        # Read the text message
        line = port.readline()
        print "The message is: %s" % line
        print "From %s on: %d/%d/%d on %d:%d:%d" % (phoneNumber, day, month, year, hour, minute, sec)
        time.sleep(1)
        reply = "Received at %d:%d:%d on %d/%d/%d" % (hour, minute, sec, month, day, year)
        SendSms(msg=reply, phoneNumber=phoneNumber)

