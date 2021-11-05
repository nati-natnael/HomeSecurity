import zmq
import cv2
import yaml
import flask
import logging
import threading
import numpy as np
import tensorflow as tf

from zmq import Socket
from time import sleep
from pathlib import Path
from flask import Response
from datetime import datetime
from collections import namedtuple
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as viz_utils

from domain import Stream, StreamSchema, ServerConfig, ModelConfig, LabelConfig

logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)

shared_stream_buffers = []


class SourceStreamThread(threading.Thread):
    def __init__(self, stream=None, model_dir=None, label_dir=None):
        super(SourceStreamThread, self).__init__()
        if stream is None:
            raise ValueError("stream required")

        self.stream: Stream = stream
        self.label_dir = label_dir
        self.model_dir = model_dir
        self.name = "SourceStreamThread"
        return

    @staticmethod
    def add_datetime_to(frame):
        if len(frame.shape) == 2:
            height, width = frame.shape
        else:
            height, width, _ = frame.shape

        datetime_string = datetime.now().strftime("%b %d, %Y %H:%M:%S")

        cv2.putText(frame, datetime_string, org=(10, height - 20),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=1,
                    color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)

    def run(self):
        logging.info(f"Source stream thread started, listening at {self.stream.port}")

        context = zmq.Context()
        socket: Socket = context.socket(zmq.SUB)
        socket.bind(f"tcp://*:{self.stream.port}")
        socket.setsockopt(zmq.CONFLATE, 1)
        socket.setsockopt_string(zmq.SUBSCRIBE, np.unicode(''))

        model = tf.saved_model.load(self.model_dir + "/saved_model")
        detect_fn = model.signatures['serving_default']

        category_index = label_map_util.create_category_index_from_labelmap(self.label_dir, use_display_name=True)

        stream_buffer = shared_stream_buffers[self.stream.id]

        while True:
            incoming_frame = socket.recv()
            np_frame = np.frombuffer(incoming_frame, dtype=np.uint8)

            frame = cv2.imdecode(np_frame, 1)

            input_tensor = tf.convert_to_tensor(frame)
            input_tensor = input_tensor[tf.newaxis, ...]

            detections = detect_fn(input_tensor)
            num_detections = int(detections.pop('num_detections'))

            detections = {key: value[0, :num_detections].numpy() for key, value in detections.items()}
            detections['num_detections'] = num_detections

            detections['detection_classes'] = detections['detection_classes'].astype(np.int64)

            viz_utils.visualize_boxes_and_labels_on_image_array(
                frame,
                detections['detection_boxes'],
                detections['detection_classes'],
                detections['detection_scores'],
                category_index,
                use_normalized_coordinates=True,
                max_boxes_to_draw=200,
                min_score_thresh=.60,
                agnostic_mode=False)

            SourceStreamThread.add_datetime_to(frame)

            cv2.imshow("image", frame)

            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

            return_val, buffer = cv2.imencode('.jpg', frame)

            stream_buffer.collection.append(buffer)


class FlaskServer:
    def __init__(self, port):
        self.port = port
        return

    @staticmethod
    def video_stream(stream_id: int):
        logging.info(f"streaming video from stream: {stream_id}")

        stream_buffer = shared_stream_buffers[stream_id]

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
            return {'streams': stream_schema.dump(shared_stream_buffers)}

        @app.route('/streams/<int:stream_id>')
        def stream_by(stream_id: int):
            return Response(FlaskServer.video_stream(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

        app.run(host="0.0.0.0", port=self.port)


class Server:
    THREAD_SLEEP = 0.0005  # in seconds

    def __init__(self):
        self.config = ServerConfig(port=8080, source_streams=[])

    def load_server_config(self, config_file_path):
        try:
            with open(config_file_path, 'r') as file:
                config_dict = yaml.safe_load(file)

                self.config.port = config_dict['port']

                model = config_dict['model']
                model_config: ModelConfig = namedtuple("ModelConfig", model.keys())(*model.values())

                label = config_dict['label']
                label_config: LabelConfig = namedtuple("LabelConfig", label.keys())(*label.values())

                model_url = f"{model_config.base_url}/{model_config.date}/{model_config.name}.tar.gz"
                self.config.model_dir = tf.keras.utils.get_file(fname=model_config.name, origin=model_url, untar=True)

                label_url = f"{label_config.base_url}/{label_config.name}"
                label_dir = tf.keras.utils.get_file(fname=label_config.name, origin=label_url, untar=False)
                self.config.label_dir = Path(label_dir)

                streams = config_dict['source-streams']
                for stream in streams:
                    source_stream = namedtuple("SourceStreamConfig", stream.keys())(*stream.values())
                    self.config.source_streams.append(source_stream)

        except IOError as e:
            logging.error(f"Exception encountered, {e}")

    def start(self):
        self.load_server_config('src/resources/application.yml')

        # Start source stream threads
        for s_stream in self.config.source_streams:
            shared_stream_buffers.append(Stream(s_stream.id, s_stream.port, s_stream.queue_size))

            s_stream_thread = SourceStreamThread(s_stream, self.config.model_dir, self.config.label_dir)
            s_stream_thread.start()

            logging.info(f"Start source stream, source id {s_stream.id}, port {s_stream.port}")

        api = FlaskServer(port=self.config.port)
        api.run()
