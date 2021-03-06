#!/usr/bin/env python
import serial,time,re   # Importing required modules
import RPi.GPIO as GPIO
import signal
import sys
import os
import glob
import datetime
import subprocess
import string
from systime import SetSystemTime

# global vars
switch1 = 24
switch2 = 26
pwrKey  = 11
timeSet = False
startTime = [0, 0]
stopTime = [0, 0]
gmtOffset = -7


sensorPresent = True
ds18b20Dev = ''


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


def WaitReturnResponse(msg):
    startTime = time.time()
    resp = port.readline()
    while (resp.find(msg) < 0):
        if (time.time() - startTime > 8):
            print "timed out :(\r\n"
            break
        resp = port.readline()
    return resp


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
    time.sleep(5)


def SendSms(msg, phoneNumber="+19286427892"):
    port.write("AT+CMGS=\"%s\"\r\n" % phoneNumber)
    WaitResponse('>')
    port.write(msg)
    port.write('\x1A')
    WaitResponse('OK')


def GetSigStatus():
    port.write("AT+CSQ\r\n")
    msg = WaitReturnResponse('+CSQ:')
    WaitResponse('OK')

    m = re.search('^\+CSQ\:\s+(\d+)\,\s*(\d+)\s*$', msg)

    if (m != None):
        rssi = int(m.group(1))
        ber = int(m.group(2))
    else:
        rssi = 99
        ber = 99

    rssiDbm = 0

    # decode RSSI to dBm
    if (rssi == 0):
        rssiDbm = -115
    elif (rssi == 1):
        rssiDbm = -111
    elif (rssi > 1 and rssi < 31):
        rssiDbm = (2 * rssi) - 114
    elif (rssi > 30):
        rssiDbm = -52

    return rssiDbm, ber


def DS18B20Init():
    global ds18b20Dev
    try:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

        # give the driver time to scan the bus
        time.sleep(1)

        # device files for DS18B20 sensors always start with 28- and take the form of 28-0000061573fa
        ds18b20DevBaseDir = '/sys/bus/w1/devices/'
        ds18b20DevDir = glob.glob(ds18b20DevBaseDir + '28*')[0]
        ds18b20Dev = ds18b20DevDir + '/w1_slave'
    except IndexError:
        print "No sensor detected"
        sensorPresent = False


def DS18B20ReadRaw():
    if (sensorPresent):
        f = open(ds18b20Dev, 'r')
        lines = f.readlines()
        f.close()
        return lines

def GetTemp():
    if (sensorPresent):
        readTries = 0;
        # the output from the tempsensor looks like this:
        # f6 01 4b 46 7f ff 0a 10 eb : crc=eb YES
        # f6 01 4b 46 7f ff 0a 10 eb t=31375

        lines = DS18B20ReadRaw()
        while (lines[0].strip()[-3:] != 'YES' and readTries < 10):
            time.sleep(0.2)
            lines = DS18B20ReadRaw()
            readTries = readTries + 1

        equals_pos = lines[1].find('t=')

        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_c, temp_f
    else:
        return -99,-99


def GetCPUTemp():
    try:
        cpuTempFile = '/sys/class/thermal/thermal_zone0/temp'
        f = open(cpuTempFile, 'r')
        lines = f.readlines()
        f.close()
        return float(lines[0]) / 1000
    except ValueError:
        return -99


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
                curHr = int(time.strftime('%H'))
                curMin = int(time.strftime('%M'))
                switch = int(m.group(2))
                startHr = int(m.group(3))
                startMin = int(m.group(4))
                durInMins = int(m.group(5))

                # calculate secs since midnight
                curSecsSinceMidnight = (curHr * 3600) + (curMin * 60)
                startSecsSinceMidnight = (startHr * 3600) + (startMin * 60)

                if (startSecsSinceMidnight < curSecsSinceMidnight):
                    startTimeTemp = time.time() + startSecsSinceMidnight + (86400 - curSecsSinceMidnight)
                else:
                    startTimeTemp = time.time() + (startSecsSinceMidnight - curSecsSinceMidnight)

                if (durInMins > 480):
                    durInMins = 480
                if (durInMins < 0):
                    durInMins = 0

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

    elif (cmd.lower() == "temp"):
        tempC, tempF = GetTemp()
        SendSms("Current temp is %.2fF, %.2fC" % (tempF, tempC), phoneNumber)

    elif (cmd.lower() == "status"):
        sw1Stat = "Nothing scheduled for sw1. "
        sw2Stat = "Nothing scheduled for sw2. "
        now = time.time()
        
        if (now < startTime[0]):
            sw1Stat = "Sw1 is scheduled to turn on in %.1f hrs for %d mins. " % (((startTime[0] - now) / 3600), (stopTime[0] - startTime[0]) / 60)
        elif (now > startTime[0] and now < stopTime[0]):
            sw1Stat = "Sw1 is currently on for %d more minutes. " % ((stopTime[0] - now) / 60)

        if (now < startTime[1]):
            sw2Stat = "Sw2 is scheduled to turn on in %.1f hrs for %d mins. " % (((startTime[1] - now) / 3600), (stopTime[1] - startTime[1]) / 60)
        elif (now > startTime[1] and now < stopTime[1]):
            sw2Stat = "Sw2 is currently on for %d more minutes. " % ((stopTime[1] - now) / 60)


        SendSms(sw1Stat + sw2Stat, phoneNumber)

    elif (cmd.lower() == "system"):
        tempC = GetCPUTemp()
        sysStatus = time.strftime("%m/%d/%Y ")
        sysStatus += subprocess.check_output('uptime')
        sysStatus += "CPU Temp: %.2f " % tempC
 
        SendSms(sysStatus, phoneNumber)

    elif (cmd.lower() == "rssi"):
        rssi, ber = GetSigStatus()
        SendSms("RSSI: %d dBm, BER: %d" % (rssi, ber), phoneNumber)


def UpdateSwitches():
    if (time.time() > startTime[0] and time.time() < stopTime[0]):
        SetSwitch1(True)
    else:
        SetSwitch1(False)

    if (time.time() > startTime[1] and time.time() < stopTime[1]):
        SetSwitch2(True)
    else:
        SetSwitch2(False)



# enable the temperature sensor
DS18B20Init()

# power up the SIM900
ModemPwrSwitch()

# setup SIM900
port.write('AT+CMGF=1\r\n')              # set text mode
WaitResponse('OK')
port.write('AT+CNMI=2,2,0,0,0\r\n')      # Output texts asynchronously
WaitResponse('OK')
port.write('AT+CLTS=1\r\n')              # use network time to set internal clock
WaitResponse('OK')


while 1: # For Infinite execution
    line = port.readline() # Check for incoming serial messages
    # a txt message will look like +CMT: "+19286427892","","14/11/19,00:37:33-28"
    if(line.startswith("+CMT:")):
        try:
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

        except:
            print "Malformed message: " + line + "\n"

        try:
            # Read the text message.
            line = port.readline()
            # check for UCS2 encoding. Not super robust but should work for the messages we expect in this application.
            if(re.match('^([0-9A-F]{4}){4,}', line)): # a UCS2 message looks like this: 004F006E00200032002000310030
                tmp =  bytearray.fromhex(line.rstrip()).decode()
                # throw away non-printing characters
                printable = set(string.printable)
                line = filter(lambda x: x in printable, tmp)
            
            ProcessCmd(line, phoneNumber)
            print "From %s on: %d/%d/%d on %d:%d:%d" % (phoneNumber, day, month, year, hour, minute, sec)
        except Exception as e:
            print "Invalid text msg: " + line
            print(e)

    UpdateSwitches()
