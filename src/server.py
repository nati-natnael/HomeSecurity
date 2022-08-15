import re
import yaml
import math
import flask
import socket
import logging
import threading

from time import sleep
from flask import Response
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


class SourceStreamThread(threading.Thread):
    DATA_BYTE_COUNT = 60000
    START_CHARS = 'START'
    START_CHARS_BYTE = b'START'

    def __init__(self, stream=None):
        super(SourceStreamThread, self).__init__()
        if stream is None:
            raise ValueError('source stream required')

        self.name = 'SourceStreamThread'
        self.stream: Stream = stream
        return

    def run(self):
        logging.info(f'Source stream started, listening at port {self.stream.port}')

        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(('0.0.0.0', self.stream.port))

        stream_buffer = shared_stream_buffers[self.stream.id]

        while True:
            incoming_frame = b''

            try:
                incoming_bytes, _ = server.recvfrom(14)

                if not re.match(b'^START,\\d{8}$', incoming_bytes):
                    continue

                start_sequence = incoming_bytes.decode('utf-8').split(',')

                byte_count = int(start_sequence[1])

                read_count = math.ceil(byte_count / SourceStreamThread.DATA_BYTE_COUNT)

                for x in range(0, byte_count, SourceStreamThread.DATA_BYTE_COUNT):
                    start = x
                    end = start + SourceStreamThread.DATA_BYTE_COUNT

                    if end > byte_count:
                        end = byte_count

                    read_byte_count = end - start

                    message, _ = server.recvfrom(read_byte_count)

                    if not re.match(b'^START,\\d{8}$', incoming_bytes):
                        raise Exception('invalid start message sequence')

                    incoming_frame += message

                stream_buffer.collection.append(incoming_frame)
            except OSError as _:
                # ignore
                pass
            except Exception as ex:
                logging.error(f'unknown error: {ex}')


class Server:
    THREAD_SLEEP = 0.0005  # in seconds

    def __init__(self, config_file_path):
        self.config_file_path = config_file_path

    def start(self):
        port = 8080
        sources = []

        try:
            with open(self.config_file_path, 'r') as file:
                config = yaml.safe_load(file)

                port = config.get('port')
                source_streams = config.get('source_streams')

                streams = []
                if source_streams:
                    streams = source_streams

                for stream in streams:
                    source = namedtuple('SourceStreamConfig', stream.keys())(*stream.values())
                    sources.append(source)

        except IOError as e:
            logging.error(f'Exception encountered, {e}')

        # Config values
        source_config = ''
        for i, source in enumerate(sources):
            source_config += \
                f'''
                \t#{i + 1} -> id: {source.id}, port: {source.port}, queue size: {source.queue_size}'''

        logging.info(
            f'''
            configs
                port    : {port}
                sources : {source_config}
            '''
        )

        if not sources:
            logging.info('no stream sources configured. server has stopped')
            return

        # Start source stream threads
        for source in sources:
            shared_stream_buffers.append(Stream(source.id, source.port, source.queue_size))
            SourceStreamThread(source).start()

        # This server handles stream requests from users
        app = flask.Flask('API')

        @app.route('/streams')
        def stream_info():
            stream_schema = StreamSchema(many=True)
            return {'streams': stream_schema.dump(shared_stream_buffers)}

        @app.route('/streams/<int:stream_id>')
        def stream_by(stream_id: int):
            return Response(stream_video(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

        app.run(host='0.0.0.0', port=port)
