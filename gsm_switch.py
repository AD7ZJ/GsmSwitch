#!/usr/bin/env python
import time
import re
import signal
import sys
import os
import glob
import datetime
import subprocess
import string


class GsmSwitch:
    def __init__(self, hardwareInterface):        
        # global vars
        self.startTime = [0, 0]
        self.stopTime = [0, 0]

        self.io = hardwareInterface
        self.gmtOffset = -7

    # Init the modem as needed for application to function
    def InitSim7600Modem(self):
        self.io.write('AT+CMGF=1\r\n')  # set text mode
        self.WaitResponse('OK')
        self.io.write('AT+CNMI=2,2,0,0,0\r\n')  # Output texts asynchronously
        self.WaitResponse('OK')

    def WaitResponse(self, msg):
        startTime = time.time()
        resp = self.io.readline()
        while msg not in resp:
            print(f"Waiting... {resp}\r\n")
            if time.time() - startTime > 8:
                print("timed out :(\r\n")
                break
            resp = self.io.readline()
        print(f"Got: {resp}")

    def WaitReturnResponse(self, msg):
        startTime = time.time()
        resp = self.io.readline()
        while msg not in resp:
            if time.time() - startTime > 8:
                print("timed out :(\r\n")
                break
            resp = self.io.readline()
        return resp

    def SendSms(self, msg, phoneNumber="+19286427892"):
        self.io.write(f"AT+CMGS=\"{phoneNumber}\"\r\n")
        self.WaitResponse('>')
        self.io.write(msg)
        self.io.write('\x1A')
        self.WaitResponse('OK')

    def GetSigStatus(self):
        self.io.write("AT+CSQ\r\n")
        msg = self.WaitReturnResponse('+CSQ:')
        self.WaitResponse('OK')

        m = re.search(r'^\+CSQ\:\s+(\d+)\,\s*(\d+)\s*$', msg)

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

    def ProcessCmd(self, command, phoneNumber, timeNow):
        m = re.search(r'^(\w+)', command)
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
                    self.startTime[0] = timeNow
                    self.stopTime[0] = timeNow + (60 * durInMins)
                    self.SendSms(f"OK, turning sw1 on now for {durInMins} minutes", phoneNumber)
                elif switch == 2:
                    self.startTime[1] = timeNow
                    self.stopTime[1] = timeNow + (60 * durInMins)
                    self.SendSms(f"OK, turning sw2 on now for {durInMins} minutes", phoneNumber)

            else:
                m = re.search(r'^(\w+)\s+(\d+)\s+(\d+)\:(\d+)\s+(\d+)\s*$', command)
                if m:
                    curHr = int(time.strftime('%H', time.gmtime(timeNow + (self.gmtOffset*3600))))
                    curMin = int(time.strftime('%M', time.gmtime(timeNow + (self.gmtOffset*3600))))
                    switch = int(m.group(2))
                    startHr = int(m.group(3))
                    startMin = int(m.group(4))
                    durInMins = int(m.group(5))

                    # calculate secs since midnight
                    curSecsSinceMidnight = (curHr * 3600) + (curMin * 60)
                    startSecsSinceMidnight = (startHr * 3600) + (startMin * 60)

                    if startSecsSinceMidnight < curSecsSinceMidnight:
                        startTimeTemp = timeNow + startSecsSinceMidnight + (86400 - curSecsSinceMidnight)
                    else:
                        startTimeTemp = timeNow + (startSecsSinceMidnight - curSecsSinceMidnight)

                    if durInMins > 480:
                        durInMins = 480
                    if durInMins < 0:
                        durInMins = 0

                    stopTimeTemp = startTimeTemp + (durInMins * 60)

                    if switch == 1:
                        self.startTime[0] = startTimeTemp
                        self.stopTime[0] = stopTimeTemp
                        self.SendSms(f"Ok, sw1 will turn on at {startHr:02d}:{startMin:02d} for {durInMins} minutes", phoneNumber)
                    elif switch == 2:
                        self.startTime[1] = startTimeTemp
                        self.stopTime[1] = stopTimeTemp
                        self.SendSms(f"Ok, sw2 will turn on at {startHr:02d}:{startMin:02d} for {durInMins} minutes", phoneNumber)
                    else:
                        self.SendSms("Err: Must specify a switch number", phoneNumber)

                else:
                    # Unrecognized msg
                    self.SendSms('Err: mangled command', phoneNumber)

        elif cmd.lower() == "off":
            m = re.search(r'^(\w+)\s+(\d+)\s*$', command)
            if m:
                switch = int(m.group(2))
                if switch == 1:
                    if self.startTime[0] != 0:
                        self.startTime[0] = 0
                        self.stopTime[0] = 0
                        self.SendSms("OK, turning sw1 off", phoneNumber)
                    else:
                        self.SendSms("sw1 is already off", phoneNumber)
                elif switch == 2:
                    if self.startTime[1] != 0:
                        self.startTime[1] = 0
                        self.stopTime[1] = 0
                        self.SendSms("OK, turning sw2 off", phoneNumber)
                    else:
                        self.SendSms("sw2 is already off", phoneNumber)
                else:
                    self.SendSms("Err: Must specify switch 1 or 2", phoneNumber)
            else:
                if self.startTime[0] != 0:
                    self.startTime[0] = 0
                    self.stopTime[0] = 0
                    self.SendSms("OK, turning sw1 off", phoneNumber)
                if self.startTime[1] != 0:
                    self.startTime[1] = 0
                    self.stopTime[1] = 0
                    self.SendSms("OK, turning sw2 off", phoneNumber)

        elif cmd.lower() == "temp":
            tempC, tempF = self.io.GetTemp()
            self.SendSms(f"Current temp is {tempF:.2f}F, {tempC:.2f}C", phoneNumber)

        elif cmd.lower() == "status":
            sw1Stat = "Nothing scheduled for sw1. "
            sw2Stat = "Nothing scheduled for sw2. "
            now = timeNow
            
            if now < self.startTime[0]:
                sw1Stat = f"Sw1 is scheduled to turn on in {((self.startTime[0] - now) / 3600):.1f} hrs for {((self.stopTime[0] - self.startTime[0]) / 60):.0f} mins. "
            elif now > self.startTime[0] and now < self.stopTime[0]:
                sw1Stat = f"Sw1 is currently on for {((self.stopTime[0] - now) / 60):.0f} more minutes. "

            if now < self.startTime[1]:
                sw2Stat = f"Sw2 is scheduled to turn on in {((self.startTime[1] - now) / 3600):.1f} hrs for {((self.stopTime[1] - self.startTime[1]) / 60):.0f} mins. "
            elif now > self.startTime[1] and now < self.stopTime[1]:
                sw2Stat = f"Sw2 is currently on for {((self.stopTime[1] - now) / 60):.0f} more minutes. "

            self.SendSms(sw1Stat + sw2Stat, phoneNumber)

        elif cmd.lower() == "system":
            tempC = self.io.GetCPUTemp()
            sysStatus = time.strftime("%m/%d/%Y ", time.gmtime(timeNow + (self.gmtOffset*3600)))
            sysStatus += subprocess.check_output('uptime', shell=True).decode('utf-8')
            sysStatus += f"CPU Temp: {tempC:.1f} "

            self.SendSms(sysStatus, phoneNumber)

        elif cmd.lower() == "rssi":
            rssi, ber = self.GetSigStatus()
            self.SendSms(f"RSSI: {rssi} dBm, BER: {ber}", phoneNumber)

    def UpdateSwitches(self):
        if time.time() > self.startTime[0] and time.time() < self.stopTime[0]:
            self.io.SetSwitch1(True)
        else:
            self.io.SetSwitch1(False)

        if time.time() > self.startTime[1] and time.time() < self.stopTime[1]:
            self.io.SetSwitch2(True)
        else:
            self.io.SetSwitch2(False)

    def CheckForMessages(self):
        line = self.io.readline()  # Check for incoming serial messages
        # a txt message will look like +CMT: "+19286427892","","14/11/19,00:37:33-28"
        if line.startswith("+CMT:"):
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

            except Exception as e:
                print(f"Malformed message: {line}\n")

            try:
                # Read the text message.
                line = self.io.readline()
                # check for UCS2 encoding. Not super robust but should work for the messages we expect in this application.
                if re.match(r'^([0-9A-F]{4}){4,}', line):  # a UCS2 message looks like this: 004F006E00200032002000310030
                    tmp = bytearray.fromhex(line.rstrip()).decode()
                    # Filter out non-printing characters
                    line = ''.join([char for char in tmp if char in string.printable])
                
                self.ProcessCmd(line, phoneNumber, time.time())
                print(f"From {phoneNumber} on: {day}/{month}/{year} at {hour}:{minute}:{sec}")
            except Exception as e:
                print(f"Invalid text msg: {line}")
                print(e)

