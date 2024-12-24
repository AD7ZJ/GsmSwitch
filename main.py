#!/usr/bin/env python
import signal
import sys
from hardware import HwInterface
from gsm_switch import GsmSwitch

class RpiGsmSwitch:
    def __init__(self): 
        self.io = HwInterface()
        self.switch = GsmSwitch(self.io)

        signal.signal(signal.SIGINT, self.sigHandler)

        # enable the temperature sensor if it exists
        self.io.DS18B20Init()

        # initialize the modem
        self.switch.InitSim7600Modem()

    # used to catch ctrl-c
    def sigHandler(self, signal, frame):
        print('Caught SIGINT, exiting...\n')
        self.io.cleanup()
        sys.exit(0)

    def Run(self):
        while True:  # For Infinite execution
            self.switch.CheckForMessages()
            self.switch.UpdateSwitches()


if __name__ == "__main__":
    rpiSwitch = RpiGsmSwitch()
    
    # Start running
    rpiSwitch.Run()

