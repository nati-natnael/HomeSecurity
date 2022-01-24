import yaml
import flask
import socket
import logging
import threading
import numpy as np
import tensorflow as tf

from time import sleep
from pathlib import Path
from flask import Response
from src.main.domain import *
from collections import namedtuple
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as viz_utils


logging.basicConfig(format="%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s", level=logging.DEBUG)

shared_stream_buffers = []


def load_server_config(config_file_path):
    _config = ServerConfig(port=8080, source_streams=[])

    try:
        with open(config_file_path, 'r') as file:
            config_dict = yaml.safe_load(file)

            _config.port = config_dict['port']

            model = config_dict['model']
            model_config: ModelConfig = namedtuple("ModelConfig", model.keys())(*model.values())

            label = config_dict['label']
            label_config: LabelConfig = namedtuple("LabelConfig", label.keys())(*label.values())

            model_url = f"{model_config.base_url}/{model_config.date}/{model_config.name}.tar.gz"
            _config.model_dir = tf.keras.utils.get_file(fname=model_config.name, origin=model_url, untar=True)

            label_url = f"{label_config.base_url}/{label_config.name}"
            label_dir = tf.keras.utils.get_file(fname=label_config.name, origin=label_url, untar=False)
            _config.label_dir = Path(label_dir)

            streams = config_dict['source-streams']
            for stream in streams:
                source_stream = namedtuple("SourceStreamConfig", stream.keys())(*stream.values())
                _config.source_streams.append(source_stream)

    except IOError as e:
        logging.error(f"Exception encountered, {e}")

    return _config


def start_flask_server(ip, port):
    app = flask.Flask("API")

    @app.route('/streams')
    def stream_info():
        stream_schema = StreamSchema(many=True)
        return {'streams': stream_schema.dump(shared_stream_buffers)}

    @app.route('/streams/<int:stream_id>')
    def stream_by(stream_id: int):
        def video_stream():
            logging.info(f"streaming video from stream: {stream_id}")

            stream_buffer = shared_stream_buffers[stream_id]

            while True:
                if stream_buffer.collection:
                    image = stream_buffer.collection[0]
                    yield b' --frame\r\n' b'Content-type: image/jpeg\r\n\r\n' + image + b'\r\n'

        return Response(video_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

    app.run(host="0.0.0.0", port=port)


def listen_from_source_stream(stream=None, model_dir=None, label_dir=None):
    logging.info(f"Source stream thread started, listening at {stream.port}")

    socket_conn = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    socket_conn.bind(("127.0.0.1", stream.port))

    # model = tf.saved_model.load(model_dir + "/saved_model")
    # detect_fn = model.signatures['serving_default']
    #
    # category_index = label_map_util.create_category_index_from_labelmap(label_dir, use_display_name=True)

    stream_buffer = shared_stream_buffers[stream.id]

    while True:
        address_pair = socket_conn.recvfrom(65535)
        incoming_frame = address_pair[0]
        address = address_pair[1]

        logging.info(f"Received message from {address}")

        # np_frame = np.frombuffer(incoming_frame, dtype=np.uint8)
        # frame = cv2.imdecode(np_frame, 1)
        #
        # input_tensor = tf.convert_to_tensor(frame)
        # input_tensor = input_tensor[tf.newaxis, ...]
        #
        # detections = detect_fn(input_tensor)
        # num_detections = int(detections.pop('num_detections'))
        #
        # detections = {key: value[0, :num_detections].numpy() for key, value in detections.items()}
        # detections['num_detections'] = num_detections
        #
        # detections['detection_classes'] = detections['detection_classes'].astype(np.int64)
        #
        # viz_utils.visualize_boxes_and_labels_on_image_array(
        #     frame,
        #     detections['detection_boxes'],
        #     detections['detection_classes'],
        #     detections['detection_scores'],
        #     category_index,
        #     use_normalized_coordinates=True,
        #     max_boxes_to_draw=200,
        #     min_score_thresh=.60,
        #     agnostic_mode=False)
        #
        # return_val, buffer = cv2.imencode('.jpg', frame)
        #
        # stream_buffer.collection.append(buffer.tobytes())
        stream_buffer.collection.append(incoming_frame)


if __name__ == '__main__':
    config = load_server_config('src/resources/application.yml')

    # Start source stream threads
    for s_stream in config.source_streams:
        shared_stream_buffers.append(Stream(s_stream.id, s_stream.port, s_stream.queue_size))

        t = threading.Thread(target=listen_from_source_stream, args=(s_stream, config.model_dir, config.label_dir))
        t.start()

        logging.info(f"Start source stream, source id {s_stream.id}, port {s_stream.port}")

    start_flask_server("0.0.0.0", config.port)
