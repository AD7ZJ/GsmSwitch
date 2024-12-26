import unittest
from gsm_switch import GsmSwitch
import re

import time

class HwInterface:
    def __init__(self):
        # 
        self.switch1State = True
        self.switch2State = True

        self.writeCalls = []
        self.readResponses = []

    def cleanup(self):
        return 0

    def readline(self):
        return self.readResponses.pop(0)
    
    def write(self, msg):
        self.writeCalls.append(msg)
        return 0
    
    def SetSwitch1(self, state):
        self.switch1State = state

    def SetSwitch2(self, state):
        self.switch2State = state

    def GetTemp(self):
        # tempC, tempF
        return 0, 32

    def GetCPUTemp(self):
        return 35


class TestGsmSwitch(unittest.TestCase):
    def test_send_sms(self):
        io = HwInterface()
        switch = GsmSwitch(io)
        #prepare modem responses
        io.readResponses = [">", "OK"]

        switch.SendSms("test message")

        #self.assertTrue(all(isinstance(item, bytes) for item in io.writeCalls))

        self.assertEqual(io.writeCalls[0], 'AT+CMGS="+19286427892"\r\n')
        self.assertEqual(io.writeCalls[1], 'test message')
        self.assertEqual(io.writeCalls[2], '\x1a')


    def test_get_sig_status(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "+CSQ: 18,99", "OK"]
        rssi, dbm = switch.GetSigStatus()

        self.assertEqual(io.writeCalls[0], 'AT+CSQ\r\n')
        self.assertEqual(rssi, -78)
        
    def test_process_cmd_on_1(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = time.time()        

        switch.ProcessCmd("on 1 120", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'OK, turning sw1 on now for 120 minutes')
        self.assertEqual(timeNow, switch.startTime[0])
        self.assertEqual(timeNow + (120 * 60), switch.stopTime[0])

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("off", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'OK, turning sw1 off')
        self.assertEqual(0, switch.startTime[0])


    def test_process_cmd_on_2(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)       

        switch.ProcessCmd("on 1 11:34 120", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Ok, sw1 will turn on at 11:34 for 120 minutes')
        self.assertEqual(timeNow + (75 * 60), switch.startTime[0])
        self.assertEqual(timeNow + (195 * 60), switch.stopTime[0])

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("off 1", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'OK, turning sw1 off')
        self.assertEqual(0, switch.startTime[0])

    def test_process_cmd_on_3(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)       

        # in this case, switch should be turned on at 10 am tomorrow (1421 min into the future)
        switch.ProcessCmd("on 2 10:00 120", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Ok, sw2 will turn on at 10:00 for 120 minutes')
        self.assertEqual(timeNow + (1421 * 60), switch.startTime[1])
        self.assertEqual(timeNow + (1541 * 60), switch.stopTime[1])

    def test_process_cmd_off(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)

        # verify it works with binary objects as well (the b)
        switch.ProcessCmd("off 1", "+1234567890", timeNow)

        self.assertEqual(io.writeCalls[1], 'sw1 is already off')
        self.assertEqual(0, switch.startTime[0])

    def test_process_cmd_status_1(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)

        # turn on switch 1
        switch.ProcessCmd("on 1 10:00 120", "+1234567890", timeNow)

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("status", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Sw1 is scheduled to turn on in 23.7 hrs for 120 mins. Nothing scheduled for sw2. ')
        
        # skip ahead 24 hours now
        timeNow += 24 * 3600

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("status", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Sw1 is currently on for 101 more minutes. Nothing scheduled for sw2. ')
        
    def test_process_cmd_status_2(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)

        # turn on switch 2
        switch.ProcessCmd("on 2 10:00 120", "+1234567890", timeNow)

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("status", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Nothing scheduled for sw1. Sw2 is scheduled to turn on in 23.7 hrs for 120 mins. ')
        
        # skip ahead 24 hours now
        timeNow += 24 * 3600

        #prepare modem responses
        io.readResponses = [">", "OK"]
        # clear out previous writes
        io.writeCalls = []

        switch.ProcessCmd("status", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], 'Nothing scheduled for sw1. Sw2 is currently on for 101 more minutes. ')
     
    def test_process_cmd_system(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)

        # send system cmd
        switch.ProcessCmd("system", "+1234567890", timeNow)
        # '12/23/2024  15:41:55 up 22:33,  1 user,  load average: 0.43, 0.53, 0.54\nCPU Temp: 35.0 '
        match = re.match(r'^.*\nCPU Temp: (\d+\.\d+)\s*$', io.writeCalls[1])
        self.assertTrue(match)
        self.assertEqual(match.group(1), '35.0')

    def test_process_cmd_rssi(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = [">", "+CSQ: 18,99", "OK", ">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)

        # send system cmd
        switch.ProcessCmd("rssi", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[2], 'RSSI: -78 dBm, BER: 99')


    def test_check_for_messages(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses
        io.readResponses = ['+CMT: "+1234567890","","24/12/23,15:19:39-32"', "on 1 120",
                            ">", "OK"]
        
        switch.CheckForMessages()

        self.assertEqual(io.writeCalls[1], 'OK, turning sw1 on now for 120 minutes')
        self.assertAlmostEqual(time.time(), switch.startTime[0], delta=1)


    def test_check_for_messages_ucs(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare modem responses. This encodes a 'status' txt messages that's UCS2 encoded
        io.readResponses = ['+CMT: "+1234567890","","24/12/23,15:19:39-32"', "005300740061007400750073",
                            ">", "OK"]
        
        switch.CheckForMessages()

        self.assertEqual(io.writeCalls[1], 'Nothing scheduled for sw1. Nothing scheduled for sw2. ')    


if __name__ == "__main__":#
    unittest.main()

