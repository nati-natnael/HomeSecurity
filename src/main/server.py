import zmq
import cv2
import yaml
import flask
import logging
import threading
import numpy as np
import tensorflow as tf

from time import sleep
from pathlib import Path
from flask import Response
from datetime import datetime
from domain import Stream, StreamSchema
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as viz_utils

logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)

stream_buffers = []
class_label = []


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
        cv2.putText(source_image, datetime_string, org, Server.FONT, font_scale, Server.TEXT_COLOR, thickness,
                    cv2.LINE_AA)

    def run(self):
        logging.info(f"Source stream thread started, listening at {self.port}")

        context = zmq.Context()
        footage_socket = context.socket(zmq.SUB)
        footage_socket.bind(f"tcp://*:{self.port}")
        footage_socket.setsockopt(zmq.CONFLATE, 1)
        footage_socket.setsockopt_string(zmq.SUBSCRIBE, np.unicode(''))

        # vid = cv2.VideoCapture(0)

        model_date = "20200711"
        model_name = "ssd_mobilenet_v2_320x320_coco17_tpu-8"
        base_url = "http://download.tensorflow.org/models/object_detection/tf2"
        model_dir = tf.keras.utils.get_file(fname=model_name, origin=f"{base_url}/{model_date}/{model_name}.tar.gz", untar=True)

        filename = 'mscoco_label_map.pbtxt'
        base_url = 'https://raw.githubusercontent.com/tensorflow/models/master/research/object_detection/data'
        label_dir = tf.keras.utils.get_file(fname=filename, origin=f"{base_url}/{filename}", untar=False)
        label_dir = Path(label_dir)

        model = tf.saved_model.load(model_dir + "/saved_model")
        detect_fn = model.signatures['serving_default']

        category_index = label_map_util.create_category_index_from_labelmap(label_dir, use_display_name=True)

        while True:
            frame = footage_socket.recv()
            np_image = np.frombuffer(frame, dtype=np.uint8)

            source = cv2.imdecode(np_image, 1)

            # ret, source = vid.read()

            input_tensor = tf.convert_to_tensor(source)
            input_tensor = input_tensor[tf.newaxis, ...]

            detections = detect_fn(input_tensor)
            num_detections = int(detections.pop('num_detections'))

            detections = {key: value[0, :num_detections].numpy() for key, value in detections.items()}
            detections['num_detections'] = num_detections

            detections['detection_classes'] = detections['detection_classes'].astype(np.int64)

            viz_utils.visualize_boxes_and_labels_on_image_array(
                source,
                detections['detection_boxes'],
                detections['detection_classes'],
                detections['detection_scores'],
                category_index,
                use_normalized_coordinates=True,
                max_boxes_to_draw=200,
                min_score_thresh=.60,
                agnostic_mode=False)

            SourceStreamThread.add_datetime_to(source)

            cv2.imshow("image", source)

            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

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
    PATH = Path().absolute()
    RESOURCE_PATH = f"{PATH}/src/resources"
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
