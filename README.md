
# SMS Controlled Switch using a raspberry pi

This code interacts with a SIM7600 4g module using AT commands over the serial port.  It uses the module to send and receive text messages for the purpose of controlling one more more switches.  I use this to turn a preheater on and off for my airplane, but it probably has other uses too :-) It started out for a SIM900 module which stopped working when TMobile shut down their 2g network. The AT commands are pretty much the same for both though. 

## Setup

On a raspian minimal image, install the following modules:
```
apt install python3
apt install python3-serial
apt install python3-rpi.gpio
```
If you want a 1-wire temp sensor to be detected, add the following lines to /etc/modules
```
w1-gpio
w1-therm
```

## Commands

### 1. **On Command**
- **Syntax:**  
  `On <switchID> <time> <duration>`  
  **Description:** Schedules `<switchID>` to turn on in the future at `<time>` for `<duration>` minutes.  

  **Example:**  
  `On 1 18:30 15`  
  (Turns switch 1 on at 18:30 for 15 minutes.)

- **Syntax:**  
  `On <switchID> <duration>`  
  **Description:** Turns `<switchID>` on immediately for `<duration>` minutes.  

  **Example:**  
  `On 2 10`  
  (Turns switch 2 on now for 10 minutes.)

### 2. **Off Command**
- **Syntax:**  
  `Off <switchID>`  
  **Description:** Turns `<switchID>` off.  

  **Example:**  
  `Off 1`  
  (Turns switch 1 off.)

- **Syntax:**  
  `Off`  
  **Description:** Turns off all switches.  

  **Example:**  
  `Off`  
  (Turns all switches off.)

### 3. **Temp Command**
- **Syntax:**  
  `Temp`  
  **Description:** Returns the current temperature as measured by the external DS18B probe.  

### 4. **Status Command**
- **Syntax:**  
  `Status`  
  **Description:** Returns the status of the switches, including whether they are on or scheduled to turn on.  
