import zmq
import cv2
import numpy
import socket
import logging
import threading
import collections

from time import sleep
from datetime import datetime

logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)

stream_buffer = collections.deque(maxlen=5)


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
        self.udp_conn = None
        self.connected = False
        self.last_message_dt = datetime.utcnow()

    def send(self, message):
        if not self.connected:
            self.udp_conn = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.udp_conn.connect((self.ip, self.port))

        # if message.size > 60000:
        #     test = "hello"
        self.udp_conn.send(message)

        logging.info(f"Sent message to client at {self.ip}:{self.port} - message size {message.size}")


class SourceStreamThread(threading.Thread):
    def __init__(self, target=None, name=None):
        super(SourceStreamThread, self).__init__()
        self.target = target
        self.name = name
        self.port = 5555
        return

    def run(self):
        logging.info(f"Source stream thread started, listening at {self.port}")

        context = zmq.Context()
        footage_socket = context.socket(zmq.SUB)
        footage_socket.bind(f"tcp://*:{self.port}")
        footage_socket.setsockopt_string(zmq.SUBSCRIBE, numpy.unicode(''))

        while True:
            frame = footage_socket.recv()
            np_image = numpy.frombuffer(frame, dtype=numpy.uint8)
            source = cv2.imdecode(np_image, 1)

            mirror_source = cv2.flip(source, 1)
            add_datetime_to(mirror_source)

            return_val, buffer = cv2.imencode('.jpg', mirror_source)

            stream_buffer.append(buffer)


class ClientStreamThread(threading.Thread):
    def __init__(self, target=None, name=None):
        super(ClientStreamThread, self).__init__()
        self.target = target
        self.name = name
        return

    def run(self):
        logging.info("Client stream thread started")

        while True:
            if stream_buffer and Server.connected_clients:
                image = stream_buffer.popleft()

                for client in Server.connected_clients:
                    client.send(image)

            sleep(Server.THREAD_SLEEP)


class Server:
    THREAD_SLEEP = 0.0005  # in seconds
    BUFFER_SIZE = 62000

    connected_clients: list[Client] = []

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def start(self):
        udp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udp_server_socket.bind((self.ip, self.port))

        logging.info(f"Server started, listening at port {self.port}")

        source_stream = SourceStreamThread(name="SourceStreamThread")
        client_stream = ClientStreamThread(name="ClientStreamThread")

        source_stream.start()
        client_stream.start()

        while True:
            message, address = udp_server_socket.recvfrom(Server.BUFFER_SIZE)

            logging.info(f"Received message {message} from {address}")

            new_client = Client(ip=address[0], port=address[1])
            Server.connected_clients.append(new_client)

            logging.info(f"New client connected - {address}")

            sleep(1)
