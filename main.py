#!/usr/bin/env python
import serial,time,re   # Importing required modules
import RPi.GPIO as GPIO
import signal
import sys
import datetime
from systime import SetSystemTime

# global vars
switch1 = 26
switch2 = 23
pwrKey  = 11
timeSet = False
startTime = [0, 0]
stopTime = [0, 0]
gmtOffset = -7

#setup GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(switch1, GPIO.OUT)
GPIO.setup(switch2, GPIO.OUT)
GPIO.setup(pwrKey, GPIO.OUT)

#setup serial port to talk to SIM900
port = serial.Serial(baudrate=19200, port='/dev/ttyAMA0', timeout=5) # Serial port initialization

# catch ctrl-c so we can cleanup the GPIO driver
def sigHandler(signal, frame):
    print('Caught SIGINT, exiting...\n')
    ModemPwrSwitch()
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


def ModemPwrSwitch():
    GPIO.output(pwrKey, 0)
    time.sleep(1)
    GPIO.output(pwrKey, 1)
    time.sleep(2)
    GPIO.output(pwrKey, 0)
    # Give the modem time to boot up
    time.sleep(10)


def SendSms(msg, phoneNumber="+19286427892"):
    port.write("AT+CMGS=\"%s\"\r\n" % phoneNumber)
    WaitResponse('>')
    port.write(msg)
    port.write('\x1A')
    WaitResponse('OK')


def ProcessCmd(command, phoneNumber):
    m = re.search('^(\w+)', command)
    cmd = m.group(1)

    if (cmd.lower() == "on"):
        m = re.search('^(\w+)\s+(\d+)\s+(\d+)\s*$', command)
        if (m != None):
            switch = int(m.group(2))
            durInMins = int(m.group(3))

            if (durInMins > 480):
                durInMins = 480
            if (durInMins < 0):
                durInMins = 0

            if (switch == 1):
                startTime[0] = time.time()
                stopTime[0] = time.time() + (60 * durInMins)
                SendSms("OK, turning sw1 on now for %d minutes" % durInMins, phoneNumber)
            elif (switch == 2):
                startTime[1] = time.time()
                stopTime[1] = time.time() + (60 * durInMins)
                SendSms("OK, turning sw2 on now for %d minutes" % durInMins, phoneNumber)

        else:
            m = re.search('^(\w+)\s+(\d+)\s+(\d+)\:(\d+)\s+(\d+)\s*$', command)
            if (m != None):
                year = int(time.strftime('%Y'))
                month = int(time.strftime('%m'))
                day = int(time.strftime('%d'))
                switch = int(m.group(2))
                startHr = int(m.group(3))
                startMin = int(m.group(4))
                durInMins = int(m.group(5))

                if (durInMins > 480):
                    durInMins = 480
                if (durInMins < 0):
                    durInMins = 0

                timeTuple = ( year, month, day, startHr, startMin, 0, 0)
                startTimeTemp = time.mktime(datetime.datetime( *timeTuple[:6]).timetuple())
                stopTimeTemp = startTimeTemp + (durInMins * 60)

                if (switch == 1):
                    startTime[0] = startTimeTemp
                    stopTime[0] = stopTimeTemp
                    SendSms("Ok, sw1 will turn on at %02d:%02d for %d minutes" % (startHr, startMin, durInMins), phoneNumber)
                elif (switch == 2):
                    startTime[1] = startTimeTemp
                    stopTime[1] = stopTimeTemp
                    SendSms("Ok, sw2 will turn on at %02d:%02d for %d minutes" % (startHr, startMin, durInMins), phoneNumber)
                else:
                    SendSms("Err: Must specify a switch number", phoneNumber)

            else:
                # Unrecognized msg
                SendSms('Err: mangled command', phoneNumber)

    elif (cmd.lower() == "off"):
        m = re.search('^(\w+)\s+(\d+)\s*$', command)
        if (m != None):
            switch = int(m.group(2))
            print "off"

            if (switch == 1):
                if (startTime[0] != 0):
                    startTime[0] = 0
                    stopTime[0] = 0
                    SendSms("OK, turning sw1 off", phoneNumber)
                else:
                    SendSms("sw1 is already off", phoneNumber)

            elif (switch == 2):
                if (startTime[1] != 0):
                    startTime[1] = 0
                    stopTime[1] = 0
                    SendSms("OK, turning sw2 off", phoneNumber)
                else:
                    SendSms("sw2 is already off", phoneNumber)

            else:
                SendSms("Err: Must specify switch 1 or 2", phoneNumber)
        else: 
            if (startTime[0] != 0):
                startTime[0] = 0
                stopTime[0] = 0
                SendSms("OK, turning sw1 off", phoneNumber)

            if (startTime[1] != 0):
                startTime[1] = 0
                stopTime[1] = 0
                SendSms("OK, turning sw2 off", phoneNumber)


def UpdateSwitches():
    if (time.time() > startTime[0] and time.time() < stopTime[0]):
        SetSwitch1(True)
    else:
        SetSwitch1(False)

    if (time.time() > startTime[1] and time.time() < stopTime[1]):
        SetSwitch2(True)
    else:
        SetSwitch2(False)


# power up the SIM900
ModemPwrSwitch()

# setup SIM900
port.write('AT+CMGF=1\r\n')              # set text mode
port.write('AT+CNMI=2,2,0,0,0\r\n')      # Output texts asynchronously
port.write('AT+CLTS=1\r\n')              # use network time to set internal clock


while 1: # For Infinite execution
    line = port.readline() # Check for incoming serial messages

    # a txt message will look like +CMT: "+19286427892","","14/11/19,00:37:33-28"
    if(line.startswith("+CMT:")):
        #                        number     ""      day   month  year   hour  min     sec
        m = re.search('\+CMT\: \"(\+\d+)\",(.*?),\"(\d+)\/(\d+)\/(\d+),(\d+)\:(\d+)\:(\d+).*', line)
        phoneNumber = m.group(1)

        day = int(m.group(5))
        month = int(m.group(4))
        year = int(m.group(3))
        hour = int(m.group(6))
        minute = int(m.group(7))
        sec = int(m.group(8))
        
        if (not timeSet):
            SetSystemTime(hour, minute, sec, day, month, year)

        # Read the text message
        line = port.readline()
        print "The message is: %s" % line
        ProcessCmd(line, phoneNumber)
        print "From %s on: %d/%d/%d on %d:%d:%d" % (phoneNumber, day, month, year, hour, minute, sec)

    UpdateSwitches()
