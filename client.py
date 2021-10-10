import cv2
import socket
import numpy as np

msgFromClient = "Hello UDP Server"

bytesToSend = str.encode(msgFromClient)

serverAddressPort = ("127.0.0.1", 20001)

bufferSize = 62000

# Create a UDP socket at client side

UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# Send to server using created UDP socket

UDPClientSocket.sendto(bytesToSend, serverAddressPort)

while True:
    frame, address = UDPClientSocket.recvfrom(bufferSize)
    npimg = np.frombuffer(frame, dtype=np.uint8)

    source = cv2.imdecode(npimg, 1)

    cv2.imshow("Stream", source)
    cv2.waitKey(1)