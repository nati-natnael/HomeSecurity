import zmq
import cv2
import yaml
import numpy
import flask
import logging
import threading
import collections

from time import sleep
from datetime import datetime
from flask import Response, url_for


logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)


class Stream:
    def __init__(self, source_id, source_port):
        self.source_id = source_id
        self.source_port = source_port
        self.collection = collections.deque(maxlen=5)


stream_buffers: list[Stream] = []


def add_datetime_to(source_image):
    if len(source_image.shape) == 2:
        height, width = source_image.shape
    else:
        height, width, _ = source_image.shape

    now = datetime.now()
    datetime_string = now.strftime("%b %d, %Y %H:%M:%S")
    org = (10, height - 20)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    color = (0, 255, 0)
    thickness = 1
    cv2.putText(source_image, datetime_string, org, font, font_scale, color, thickness, cv2.LINE_AA)


class SourceStreamThread(threading.Thread):
    def __init__(self, stream_id=None, port=None, name=None):
        super(SourceStreamThread, self).__init__()
        self.id = stream_id
        self.port = port
        self.name = name
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

            source = cv2.flip(source, 1)
            add_datetime_to(source)

            return_val, buffer = cv2.imencode('.jpg', source)

            stream_buffers[self.id].collection.append(buffer)


class FlaskServer:
    def __init__(self, port):
        self.port = port
        return

    @staticmethod
    def video_stream(stream_id: int):
        logging.info(f"streaming video from stream: {stream_id}")

        stream_buffer = stream_buffers[stream_id]

        while True:
            if stream_buffer.collection:
                image = stream_buffer.collection[0]
                yield b' --frame\r\n' b'Content-type: image/jpeg\r\n\r\n' + image.tobytes() + b'\r\n'

            sleep(Server.THREAD_SLEEP)

    def run(self):
        app = flask.Flask("API")

        @app.route("/")
        def root():
            return "Hello"

        @app.route('/streams/<int:stream_id>')
        def camera(stream_id):

            if 0 <= stream_id < len(stream_buffers):
                return """<html>
                             <head>
                               <meta name="viewport" content="width=device-width, initial-scale=1">
                               <style>
                                  img { 
                                        display: block;
                                        margin-left: auto;
                                        margin-right: auto;
                                  }
                                  h1 { 
                                    text-align: center; 
                                  }
                                </style>
                                <title>Camera """ + str(stream_id) + """</title>
                              </head>
                              <body>
                                 <img id="bg" src=""" + url_for(f"video_feed", stream_id=stream_id) + """ style="width:88%;">
                              </body>
                            </html>
                        """
            return f"""<html>
                         <head>
                           <meta name="viewport" content="width=device-width, initial-scale=1">
                            <title></title>
                          </head>
                          <body>
                             Invalid stream ID: {stream_id}
                          </body>
                      </html>
                   """

        @app.route("/streams/stream/<int:stream_id>")
        def video_feed(stream_id: int):
            return Response(FlaskServer.video_stream(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

        app.run(host="0.0.0.0", port=self.port)


class Server:
    THREAD_SLEEP = 0.0005  # in seconds

    def __init__(self):
        self.port = 8080

    def start(self):
        try:
            with open('src/resources/application.yml', 'r') as file:
                server_config = yaml.safe_load(file)

        except IOError as e:
            logging.error(f"Exception encountered, {e}")
            server_config = None

        self.port = server_config['port'] if server_config else self.port

        source_streams = server_config['source-streams'] if server_config else []
        for source_stream in source_streams:

            stream_id = source_stream['id']
            stream_port = source_stream['port']

            stream = Stream(stream_id, stream_port)
            stream_buffers.append(stream)

            source_stream = SourceStreamThread(stream_id, stream_port, 'SourceStreamThread')
            source_stream.start()

            logging.info(f"Start source stream, source id {stream_id}, port {stream_port}")

        api = FlaskServer(port=self.port)
        api.run()
