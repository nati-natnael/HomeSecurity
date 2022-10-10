import re
import yaml
import flask
import socket
import logging

from time import sleep
from flask import Response
from flask_cors import CORS
from threading import Thread
from collections import namedtuple
from domain import Stream, StreamSchema

logging.basicConfig(format='%(asctime)s %(threadName)-9s [%(levelname)s] - %(message)s', level=logging.DEBUG)

shared_stream_buffers = []


def stream_video(stream_id: int):
    logging.info(f'streaming video from stream: {stream_id}')

    stream_buffer = shared_stream_buffers[stream_id]

    while True:
        if stream_buffer.collection:
            image = stream_buffer.collection[0]
            yield b' --frame\r\n' b'Content-type: image/jpeg\r\n\r\n' + image + b'\r\n'

        sleep(Server.THREAD_SLEEP)


class SourceStreamListener(Thread):
    START_MSG_BYTE_COUNT = 14
    DATA_BYTE_COUNT = 60000
    MAX_IMAGE_BYTE_COUNT = 500000

    def __init__(self, stream=None):
        super(SourceStreamListener, self).__init__()

        if stream is None:
            raise ValueError('source stream required')

        self.name = 'SourceStreamThread'
        self.stream: Stream = stream
        return

    def run(self):
        logging.info(f'source stream started, listening at port {self.stream.port}')

        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(('0.0.0.0', self.stream.port))

        stream_buffer = shared_stream_buffers[self.stream.id]

        start_sequence_pattern = re.compile(b'^START,\\d{8}$')

        while True:
            incoming_frame = b''

            try:
                incoming_bytes, _ = server.recvfrom(SourceStreamListener.START_MSG_BYTE_COUNT)

                # First message needs to be start sequence
                if not re.match(start_sequence_pattern, incoming_bytes):
                    raise Exception('invalid start sequence')

                start_sequence = incoming_bytes.decode('utf-8').split(',')

                byte_count = int(start_sequence[1])
                if byte_count > SourceStreamListener.MAX_IMAGE_BYTE_COUNT:
                    raise Exception(f'image size too big: {byte_count}')

                for x in range(0, byte_count, SourceStreamListener.DATA_BYTE_COUNT):
                    start = x
                    end = start + SourceStreamListener.DATA_BYTE_COUNT

                    if end > byte_count:
                        end = byte_count

                    read_byte_count = end - start

                    message, _ = server.recvfrom(read_byte_count)

                    if re.match(start_sequence_pattern, message):
                        raise Exception('invalid start message sequence')

                    incoming_frame += message

                stream_buffer.collection.append(incoming_frame)
            except OSError as _:
                # ignore
                pass
            except Exception as ex:
                logging.error(ex)

            sleep(Server.THREAD_SLEEP)


class Server:
    THREAD_SLEEP = 0.0005  # in seconds

    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.port = 8080
        self.sources = []

    def start(self):
        self.read_config()
        self.print_configs()
        self.start_source_stream_listeners()
        self.start_api()

    def read_config(self):
        try:
            with open(self.config_file_path, 'r') as file:
                config = yaml.safe_load(file)

                self.port = config.get('port')
                source_streams = config.get('source_streams')

                streams = []
                if source_streams:
                    streams = source_streams

                for stream in streams:
                    source = namedtuple('SourceStreamConfig', stream.keys())(*stream.values())
                    self.sources.append(source)

        except IOError as e:
            logging.error(f'Exception encountered, {e}')

    def print_configs(self):
        source_config = ''
        for i, source in enumerate(self.sources):
            source_config += \
                f'''
                        \t#{i + 1} -> id: {source.id}, port: {source.port}, queue size: {source.queue_size}'''

        logging.info(
            f'''
                    configs
                        port    : {self.port}
                        sources : {source_config}
                    '''
        )

    def start_source_stream_listeners(self):
        if not self.sources:
            logging.info('no stream sources configured. server has stopped')
            return

        for source in self.sources:
            stream = Stream(source.id, source.port, source.queue_size)
            shared_stream_buffers.append(stream)
            SourceStreamListener(source).start()

    def start_api(self):
        # This server handles stream requests from users
        app = flask.Flask('API')
        CORS(app)

        @app.route('/streams')
        def stream_info():
            stream_schema = StreamSchema(many=True)
            return {'streams': stream_schema.dump(shared_stream_buffers)}

        @app.route('/streams/<int:stream_id>')
        def stream_by(stream_id: int):
            return Response(stream_video(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

        app.run(host='0.0.0.0', port=self.port)
