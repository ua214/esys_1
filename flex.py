import machine
import time
import network
import json
from machine import I2C, Pin
Vsource=3.3
R2=10000
flat_resistance=10000
bend_resistance=26000

def main():
	i2c_obj=startADC()#configure the ADC to start converting Analog to Digital
	client=connect_to_network() #connect to MQTT
	send_data(i2c_obj,client)# read and send data
	
def startADC():
        #specify the pins for the i2c communnication with the peripherals and fequency used
	i2c = I2C(scl=Pin(5), sda=Pin(4), freq=100000)
	#Address of peripherals can be received using i2c.scan() command
	#Access the ADC peripheral with address 72, then access the configuration register
        #with address 1. Configuration register when initialized tells ADC to perfom a
	#continuous converstion. Achieved by the command send to register, which is b'\xc2\x03'
	i2c.writeto_mem(72,1,b'\xc2\x03')
	return i2c

def read_data(i2c):
        #Access the ADC peripheral with address 72, then access the converstion register
        #with address 0 (result of ADC conversion stored in this register)
        #and return 2 bytes since it is a 16-bit register
	data=i2c.readfrom_mem(72,0,2)
	#Transform the received 2 bytes to the equivalent digital form of volts after ADC conversion
	numb=data[0]*256+data[1]
	#Convert the digital form into volts
	volts=numb*(2*4.096/65535)
	return volts

def connect_to_network():
	ap_if = network.WLAN(network.AP_IF)
	ap_if.active(False)
	sta_if =network.WLAN(network.STA_IF)
	sta_if.active(True)
	sta_if.connect('EEERover','exhibition')
        #Keep trying until it connects to the network
	while not sta_if.isconnected():
		pass
	print('The connection was successfull')
	
	from umqtt.simple import MQTTClient
	client = MQTTClient('TTMid','192.168.0.10')
	client.connect()
	return client;

def toggle(p):
        #Toggle the led 
        p.value(not p.value())
        
def send_data(i2c,client):
        led=Pin(2,Pin.OUT)#set the pin that controls the counter blue LED as an ouput Pin
        led.high()#initialize this pin with zero volts,blue LED=off
        pin13 = Pin(13,Pin.OUT) #set the pin number 13 that controls the RED LED as an ouput Pin
        pin13.value(0)#initialize this pin with zero volts, RED LED=off
        counter=0 #initilize counter
	while True:
                volts=read_data(i2c)# call read_data() function to receive volts measurement
		flex=False#boolean that keeps track whether flex sensor was flexed more that 10 sec
                if (volts<1.6): #if sensor is flexed voltage falls below this threshold then
                        counter=counter+1#start counting for 10 sec
                        toggle(led) #one toggle of blue led represents half a second
                        if (volts<1.6) and (counter>10): # if it was flexed more that 10 sec then:
                                pin13.value(1) #RED LED is on
                                calc_resistance=R2*(Vsource-volts)/volts #Calculate bending resistance
                                #Calculating bending angle
                                angle_bend=(calc_resistance - flat_resistance) * 180 / (bend_resistance -flat_resistance)
                                t0=time.time() #record current instance of time in seconds
                                voltage=str(volts)+' V'
                                resistance=str(int(calc_resistance)) + ' Ohms'
                                angle= str(int(angle_bend)) + ' Degrees'
                                json_string = {'Condition': 'Flexed >10 sec', 'Bend angle': angle,
                                               'Resistance': resistance,'Voltage': voltage}
                                payload= json.dumps(json_string) #convert data send to json format
                                print(payload)
                                client.publish('esys/TTM/', bytes(payload, 'utf-8'))#send  data to broker
                                #This while loop will be used to calculated the total time of flexing
                                while volts<1.6: # when flexed for more than 10 sec, keep reading the 
                                        volts=read_data(i2c)#voltage to check if flexing has stopped
                                        t1=time.time()+ 10 #keep recording a new time instance plus the
                                        #10 seconds from before.
                                        flex=True #means that flexing is still going
                                
                else:
                        counter=0 #if flex has stopped then reinitialize counter to zero
                        pin13.value(0)#turn off RED LED
                        led.high()#turn off blue LED
                        
                if (flex): #if the sensor was flexed more that 10 seconds this if statement is activated
                        t=str(t1-t0) + ' sec'# find the difference between the two instance of time recorded
                        #in order to find the total time that the flex sensor was flexed for
                        json_string = {'Condition': 'Bending has stopped' ,'Time it was bend for: ': t}
                        payload= json.dumps(json_string)#convert data send to json format
                        print(payload)
                        client.publish('esys/TTM/', bytes(payload, 'utf-8'))#send data to broker
                        
                time.sleep(1)#run the infinite while loop every 1 second
