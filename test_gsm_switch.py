import unittest
from gsm_switch import GsmSwitch

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
        return self.readResponses.pop(0).encode('ascii')
    
    def write(self, msg):
        self.writeCalls.append(msg)
        return 0
    
    def SetSwitch1(self, state):
        self.switch1State = state

    def SetSwitch2(self, state):
        self.switch2State = state

    def GetTemp(self):
        # tempC, tempF
        return -99, -99

    def GetCPUTemp():
        return 35


class TestGsmSwitch(unittest.TestCase):
    def test_send_sms(self):
        io = HwInterface()
        switch = GsmSwitch(io)
        #prepare responses
        io.readResponses = [">", "OK"]

        switch.SendSms("test message")

        #self.assertTrue(all(isinstance(item, bytes) for item in io.writeCalls))

        self.assertEqual(io.writeCalls[0], b'AT+CMGS="+19286427892"\r\n')
        self.assertEqual(io.writeCalls[1], b'test message')
        self.assertEqual(io.writeCalls[2], b'\x1a')


    def test_get_sig_status(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare responses
        io.readResponses = [">", "+CSQ: 18,99", "OK"]
        rssi, dbm = switch.GetSigStatus()

        self.assertEqual(io.writeCalls[0], b'AT+CSQ\r\n')
        self.assertEqual(rssi, -78)
        
    def test_process_cmd_on_1(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare responses
        io.readResponses = [">", "OK"]

        timeNow = time.time()        

        switch.ProcessCmd("on 1 120", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], b'OK, turning sw1 on now for 120 minutes')
        self.assertEqual(timeNow, switch.startTime[0])
        self.assertEqual(timeNow + (120 * 60), switch.stopTime[0])


    def test_process_cmd_on_2(self):
        io = HwInterface()
        switch = GsmSwitch(io)

        #prepare responses
        io.readResponses = [">", "OK"]

        timeNow = 1734974383 # December 23, 2024 10:19:43 AM (at gmt-7)       

        switch.ProcessCmd("on 1 11:34 120", "+1234567890", timeNow)
        self.assertEqual(io.writeCalls[1], b'Ok, sw1 will turn on at 11:34 for 120 minutes')
        self.assertEqual(timeNow + (75 * 60), switch.startTime[0])
        self.assertEqual(timeNow + (195 * 60), switch.stopTime[0])



    def invalid_initialization(self):
        with self.assertRaises(TypeError):
            GsmSwitch(24)  # Missing second parameter

if __name__ == "__main__":#
    unittest.main()

