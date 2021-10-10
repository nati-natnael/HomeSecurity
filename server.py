import zmq
import cv2
import time
import socket
import logging
import threading
import numpy as np

from datetime import datetime

logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)


def add_datetime_to(source_image):
    height, width, color = source_image.shape

    now = datetime.now()
    datetime_string = now.strftime("%b %d, %Y %H:%M:%S")
    org = (10, height - 20)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    color = (0, 255, 0)
    thickness = 1
    cv2.putText(source_image, datetime_string, org, font, font_scale, color, thickness, cv2.LINE_AA)


class Client:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.connected = False
        self.last_message_dt = datetime.utcnow()

    def send_message(self, message):
        pass


class SourceStream(threading.Thread):
    def __init__(self, target=None, name=None):
        super(SourceStream, self).__init__()
        self.target = target
        self.name = name
        return

    def run(self):
        port = 5555

        logging.info(f"Listening for source at port {port}")

        context = zmq.Context()
        footage_socket = context.socket(zmq.SUB)
        footage_socket.bind("tcp://*:{}".format(port))
        footage_socket.setsockopt_string(zmq.SUBSCRIBE, np.unicode(''))

        while True:
            frame = footage_socket.recv()
            np_image = np.frombuffer(frame, dtype=np.uint8)
            source = cv2.imdecode(np_image, 1)

            add_datetime_to(source)

            cv2.imshow("Stream", source)
            cv2.waitKey(1)


class ClientStream(threading.Thread):
    def __init__(self, target=None, name=None):
        super(ClientStream, self).__init__()
        self.target = target
        self.name = name
        return

    def run(self):
        pass


class Server:
    connected_clients: list[Client] = []

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.buffer_size = 1024

    def start(self):
        udp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udp_server_socket.bind((self.ip, self.port))

        logging.info(f"Listening at port {self.port}")

        source = SourceStream(name="SourceStreamThread")
        source.start()
        source.join()

        while True:
            (message, address) = udp_server_socket.recvfrom(self.buffer_size)

            logging.info(f"Received message {message} from {address}")

            new_client = Client(ip=address[0], port=address[1])
            Server.connected_clients.append(new_client)

            logging.info(f"New client connected - {address}")

            udp_server_socket.sendto("Hello UDP Client".encode(), address)

            time.sleep(1)
