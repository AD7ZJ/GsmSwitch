import serial
import RPi.GPIO as GPIO
import time

class HwInterface:
    def setup(self):
        # set the pins used to control each switch
        self.switch1 = 24
        self.switch2 = 26

        # setup serial port to talk to SIM7600
        self.port = serial.Serial(baudrate=115200, port='/dev/ttyAMA0', timeout=5)

        self.sensorPresent = True

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.switch1, GPIO.OUT)
        GPIO.setup(self.switch2, GPIO.OUT)

    def cleanup(self):
        GPIO.cleanup()
        self.port.close()

    def readline(self):
        return self.port.readline()
    
    def write(self, msg):
        return self.port.write(msg)
    
    def SetSwitch1(self, state):
        GPIO.output(self.switch1, state)

    def SetSwitch2(self, state):
        GPIO.output(self.switch2, state) 

    def DS18B20Init(self):
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
            self.sensorPresent = False

    def DS18B20ReadRaw(self):
        if self.sensorPresent:
            with open(ds18b20Dev, 'r') as f:
                lines = f.readlines()
            return lines

    def GetTemp(self):
        if self.sensorPresent:
            readTries = 0
            # the output from the tempsensor looks like this:
            # f6 01 4b 46 7f ff 0a 10 eb : crc=eb YES
            # f6 01 4b 46 7f ff 0a 10 eb t=31375
            lines = self.DS18B20ReadRaw()
            while lines[0].strip()[-3:] != 'YES' and readTries < 10:
                time.sleep(0.2)
                lines = self.DS18B20ReadRaw()
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
