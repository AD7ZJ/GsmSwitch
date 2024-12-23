#!/usr/bin/env python
import serial
import time
import re
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

# setup GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(switch1, GPIO.OUT)
GPIO.setup(switch2, GPIO.OUT)
GPIO.setup(pwrKey, GPIO.OUT)

# setup serial port to talk to SIM900
port = serial.Serial(baudrate=115200, port='/dev/ttyAMA0', timeout=5)  # Serial port initialization

# catch ctrl-c so we can cleanup the GPIO driver
def sigHandler(signal, frame):
    print('Caught SIGINT, exiting...\n')
    GPIO.cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, sigHandler)

def WaitResponse(msg):
    startTime = time.time()
    resp = port.readline()
    while msg not in resp.decode():
        print(f"Waiting... {resp}\r\n")
        if time.time() - startTime > 8:
            print("timed out :(\r\n")
            break
        resp = port.readline()
    print(f"Got: {resp}")

def WaitReturnResponse(msg):
    startTime = time.time()
    resp = port.readline()
    while msg not in resp.decode():
        if time.time() - startTime > 8:
            print("timed out :(\r\n")
            break
        resp = port.readline()
    return resp

def SetSwitch1(state):
    GPIO.output(switch1, state)

def SetSwitch2(state):
    GPIO.output(switch2, state)

def SendSms(msg, phoneNumber="+19286427892"):
    port.write(f"AT+CMGS=\"{phoneNumber}\"\r\n".encode())
    WaitResponse('>')
    port.write(msg.encode())
    port.write(b'\x1A')
    WaitResponse('OK')

def GetSigStatus():
    port.write("AT+CSQ\r\n".encode())
    msg = WaitReturnResponse('+CSQ:')
    WaitResponse('OK')

    m = re.search(r'^\+CSQ\:\s+(\d+)\,\s*(\d+)\s*$', msg.decode())

    if m:
        rssi = int(m.group(1))
        ber = int(m.group(2))
    else:
        rssi = 99
        ber = 99

    if rssi == 0:
        rssiDbm = -115
    elif rssi == 1:
        rssiDbm = -111
    elif 1 < rssi < 31:
        rssiDbm = (2 * rssi) - 114
    else:
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
        print("No sensor detected")
        sensorPresent = False

def DS18B20ReadRaw():
    if sensorPresent:
        with open(ds18b20Dev, 'r') as f:
            lines = f.readlines()
        return lines

def GetTemp():
    if sensorPresent:
        readTries = 0
        # the output from the tempsensor looks like this:
        # f6 01 4b 46 7f ff 0a 10 eb : crc=eb YES
        # f6 01 4b 46 7f ff 0a 10 eb t=31375
        lines = DS18B20ReadRaw()
        while lines[0].strip()[-3:] != 'YES' and readTries < 10:
            time.sleep(0.2)
            lines = DS18B20ReadRaw()
            readTries += 1

        equals_pos = lines[1].find('t=')

        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_c, temp_f
    return -99, -99

def GetCPUTemp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            lines = f.readlines()
        return float(lines[0]) / 1000
    except ValueError:
        return -99

def ProcessCmd(command, phoneNumber):
    m = re.search('^(\w+)', command)
    cmd = m.group(1)

    if cmd.lower() == "on":
        m = re.search(r'^(\w+)\s+(\d+)\s+(\d+)\s*$', command)
        if m:
            switch = int(m.group(2))
            durInMins = int(m.group(3))

            if durInMins > 480:
                durInMins = 480
            if durInMins < 0:
                durInMins = 0

            if switch == 1:
                startTime[0] = time.time()
                stopTime[0] = time.time() + (60 * durInMins)
                SendSms(f"OK, turning sw1 on now for {durInMins} minutes", phoneNumber)
            elif switch == 2:
                startTime[1] = time.time()
                stopTime[1] = time.time() + (60 * durInMins)
                SendSms(f"OK, turning sw2 on now for {durInMins} minutes", phoneNumber)

        else:
            m = re.search(r'^(\w+)\s+(\d+)\s+(\d+)\:(\d+)\s+(\d+)\s*$', command)
            if m:
                curHr = int(time.strftime('%H'))
                curMin = int(time.strftime('%M'))
                switch = int(m.group(2))
                startHr = int(m.group(3))
                startMin = int(m.group(4))
                durInMins = int(m.group(5))

                # calculate secs since midnight
                curSecsSinceMidnight = (curHr * 3600) + (curMin * 60)
                startSecsSinceMidnight = (startHr * 3600) + (startMin * 60)

                if startSecsSinceMidnight < curSecsSinceMidnight:
                    startTimeTemp = time.time() + startSecsSinceMidnight + (86400 - curSecsSinceMidnight)
                else:
                    startTimeTemp = time.time() + (startSecsSinceMidnight - curSecsSinceMidnight)

                if durInMins > 480:
                    durInMins = 480
                if durInMins < 0:
                    durInMins = 0

                stopTimeTemp = startTimeTemp + (durInMins * 60)

                if switch == 1:
                    startTime[0] = startTimeTemp
                    stopTime[0] = stopTimeTemp
                    SendSms(f"Ok, sw1 will turn on at {startHr:02d}:{startMin:02d} for {durInMins} minutes", phoneNumber)
                elif switch == 2:
                    startTime[1] = startTimeTemp
                    stopTime[1] = stopTimeTemp
                    SendSms(f"Ok, sw2 will turn on at {startHr:02d}:{startMin:02d} for {durInMins} minutes", phoneNumber)
                else:
                    SendSms("Err: Must specify a switch number", phoneNumber)

            else:
                # Unrecognized msg
                SendSms('Err: mangled command', phoneNumber)

    elif cmd.lower() == "off":
        m = re.search(r'^(\w+)\s+(\d+)\s*$', command)
        if m:
            switch = int(m.group(2))
            if switch == 1:
                if startTime[0] != 0:
                    startTime[0] = 0
                    stopTime[0] = 0
                    SendSms("OK, turning sw1 off", phoneNumber)
                else:
                    SendSms("sw1 is already off", phoneNumber)
            elif switch == 2:
                if startTime[1] != 0:
                    startTime[1] = 0
                    stopTime[1] = 0
                    SendSms("OK, turning sw2 off", phoneNumber)
                else:
                    SendSms("sw2 is already off", phoneNumber)
            else:
                SendSms("Err: Must specify switch 1 or 2", phoneNumber)
        else:
            if startTime[0] != 0:
                startTime[0] = 0
                stopTime[0] = 0
                SendSms("OK, turning sw1 off", phoneNumber)
            if startTime[1] != 0:
                startTime[1] = 0
                stopTime[1] = 0
                SendSms("OK, turning sw2 off", phoneNumber)

    elif cmd.lower() == "temp":
        tempC, tempF = GetTemp()
        SendSms(f"Current temp is {tempF:.2f}F, {tempC:.2f}C", phoneNumber)

    elif cmd.lower() == "status":
        sw1Stat = "Nothing scheduled for sw1. "
        sw2Stat = "Nothing scheduled for sw2. "
        now = time.time()
        
        if now < startTime[0]:
            sw1Stat = f"Sw1 is scheduled to turn on in {((startTime[0] - now) / 3600):.1f} hrs for {((stopTime[0] - startTime[0]) / 60):d} mins. "
        elif now > startTime[0] and now < stopTime[0]:
            sw1Stat = f"Sw1 is currently on for {((stopTime[0] - now) / 60):d} more minutes. "

        if now < startTime[1]:
            sw2Stat = f"Sw2 is scheduled to turn on in {((startTime[1] - now) / 3600):.1f} hrs for {((stopTime[1] - startTime[1]) / 60):d} mins. "
        elif now > startTime[1] and now < stopTime[1]:
            sw2Stat = f"Sw2 is currently on for {((stopTime[1] - now) / 60):d} more minutes. "

        SendSms(sw1Stat + sw2Stat, phoneNumber)

    elif cmd.lower() == "system":
        tempC = GetCPUTemp()
        sysStatus = time.strftime("%m/%d/%Y ")
        sysStatus += subprocess.check_output('uptime', shell=True).decode('utf-8')
        sysStatus += f"CPU Temp: {tempC:.2f} "

        SendSms(sysStatus, phoneNumber)

    elif cmd.lower() == "rssi":
        rssi, ber = GetSigStatus()
        SendSms(f"RSSI: {rssi} dBm, BER: {ber}", phoneNumber)

def UpdateSwitches():
    if time.time() > startTime[0] and time.time() < stopTime[0]:
        SetSwitch1(True)
    else:
        SetSwitch1(False)

    if time.time() > startTime[1] and time.time() < stopTime[1]:
        SetSwitch2(True)
    else:
        SetSwitch2(False)


def InitializeSystem():
    # enable the temperature sensor
    DS18B20Init()

    # setup SIM7600
    port.write('AT+CMGF=1\r\n'.encode())  # set text mode
    WaitResponse('OK')
    port.write('AT+CNMI=2,2,0,0,0\r\n'.encode())  # Output texts asynchronously
    WaitResponse('OK')
    #port.write(b'AT+CLTS=1\r\n')  # use network time to set internal clock
    #WaitResponse('OK')


def Run():
    while True:  # For Infinite execution
        line = port.readline()  # Check for incoming serial messages
        # a txt message will look like +CMT: "+19286427892","","14/11/19,00:37:33-28"
        if line.startswith(b"+CMT:"):
            try:
                #                        number     ""      day   month  year   hour  min     sec
                m = re.search(r'\+CMT\: \"(\+\d+)\",(.*?),\"(\d+)\/(\d+)\/(\d+),(\d+)\:(\d+)\:(\d+).*', line)
                phoneNumber = m.group(1)

                day = int(m.group(5))
                month = int(m.group(4))
                year = int(m.group(3))
                hour = int(m.group(6))
                minute = int(m.group(7))
                sec = int(m.group(8))
            
                if not timeSet:
                    SetSystemTime(hour, minute, sec, day, month, year)

            except Exception as e:
                print(f"Malformed message: {line}\n")

            try:
                # Read the text message.
                line = port.readline()
                # check for UCS2 encoding. Not super robust but should work for the messages we expect in this application.
                if re.match(r'^([0-9A-F]{4}){4,}', line):  # a UCS2 message looks like this: 004F006E00200032002000310030
                    tmp = bytearray.fromhex(line.rstrip()).decode()
                    # throw away non-printing characters
                    printable = set(string.printable)
                    line = filter(lambda x: x in printable, tmp)
                
                ProcessCmd(line, phoneNumber)
                print(f"From {phoneNumber} on: {day}/{month}/{year} at {hour}:{minute}:{sec}")
            except Exception as e:
                print(f"Invalid text msg: {line}")
                print(e)

        UpdateSwitches()


if __name__ == "__main__":
    # Initialize system
    InitializeSystem()
    
    # Process incoming messages
    Run()

