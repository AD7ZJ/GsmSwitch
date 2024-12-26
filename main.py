#!/usr/bin/env python
import signal
import sys
import logging
from hardware import HwInterface
from gsm_switch import GsmSwitch

# if you want a 1-wire temp sensor to be detected, add the following lines to /etc/modules
# w1-gpio
# w1-therm

class RpiGsmSwitch:
    def __init__(self): 
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
        self.log = logging.getLogger(__name__)
        self.io = HwInterface(self.log)
        self.switch = GsmSwitch(self.io, self.log)

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

