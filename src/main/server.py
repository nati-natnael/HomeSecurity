import zmq
import cv2
import yaml
import numpy
import flask
import logging
import threading


from time import sleep
from flask import Response
from datetime import datetime

from domain import Stream, StreamSchema

logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)

stream_buffers: list[Stream] = []
class_label: list[str] = []


class SourceStreamThread(threading.Thread):
    def __init__(self, stream_id=None, port=None, name=None):
        super(SourceStreamThread, self).__init__()
        self.id = stream_id
        self.port = port
        self.name = name
        return

    @staticmethod
    def add_datetime_to(source_image):
        if len(source_image.shape) == 2:
            height, width = source_image.shape
        else:
            height, width, _ = source_image.shape

        datetime_string = datetime.now().strftime("%b %d, %Y %H:%M:%S")
        org = (10, height - 20)
        font_scale = 1
        thickness = 2
        cv2.putText(source_image, datetime_string, org, Server.FONT, font_scale, Server.TEXT_COLOR, thickness, cv2.LINE_AA)

    def run(self):
        logging.info(f"Source stream thread started, listening at {self.port}")

        context = zmq.Context()
        footage_socket = context.socket(zmq.SUB)
        footage_socket.bind(f"tcp://*:{self.port}")
        footage_socket.setsockopt_string(zmq.SUBSCRIBE, numpy.unicode(''))

        model = cv2.dnn_DetectionModel('src/resources/frozen_inference_graph.pb', 'src/resources/graph.pbtxt')
        model.setInputSize(320, 320)
        model.setInputScale(1.0/127.5)
        model.setInputMean((127.5, 127.5, 127.5))
        model.setInputSwapRB(True)

        while True:
            frame = footage_socket.recv()
            np_image = numpy.frombuffer(frame, dtype=numpy.uint8)
            source = cv2.imdecode(np_image, 1)

            SourceStreamThread.add_datetime_to(source)

            class_index, confidence, bbox = model.detect(source, confThreshold=0.5)

            flattened_class_index = class_index.flatten() if len(class_index) > 0 else []
            filtered_index_list = list(filter(lambda ind: ind == 1, flattened_class_index))

            for index in filtered_index_list:
                boxes = bbox[index - 1]
                label = class_label[index - 1]
                label_position = (boxes[0] + 10, boxes[1] + 30)

                cv2.rectangle(source, boxes, Server.BOUNDING_BOX_COLOR, 2)
                cv2.putText(source, label, label_position, Server.FONT,
                            fontScale=1, color=Server.TEXT_COLOR, thickness=2)

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

        @app.route('/streams')
        def stream_info():
            stream_schema = StreamSchema(many=True)
            return {'streams': stream_schema.dump(stream_buffers)}

        @app.route('/streams/<int:stream_id>')
        def stream_by(stream_id: int):
            return Response(FlaskServer.video_stream(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

        app.run(host="0.0.0.0", port=self.port)


class Server:
    THREAD_SLEEP = 0.0005  # in seconds
    TEXT_COLOR = (0, 255, 0)
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    BOUNDING_BOX_COLOR = (0, 255, 0)

    def __init__(self):
        self.port = 8080

    def start(self):
        try:
            with open('src/resources/application.yml', 'r') as file:
                server_config = yaml.safe_load(file)

        except IOError as e:
            logging.error(f"Exception encountered, {e}")
            server_config = None

        try:
            with open('src/resources/coco.names', 'r') as file:
                class_label.extend(file.read().rstrip('\n').split('\n'))

        except IOError as e:
            logging.error(f"Exception encountered, {e}")

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
