import serial
import time

port = input("COM-port COM1: ")

# Cisco-konsoll: 9600 baud, 8 databit, ingen paritet, 1 stoppbit
ser = serial.Serial(port, baudrate=9600, timeout=1)

ser.write(b"\r")          # trykk Enter
time.sleep(2)             # gi enheten tid til å svare
svar = ser.read(ser.in_waiting).decode(errors="ignore")
print("Enheten svarte:")
print(svar)

ser.close()