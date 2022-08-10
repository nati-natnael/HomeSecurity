import collections

from marshmallow import Schema, fields


class StreamSchema(Schema):
    id = fields.Int()


class Stream:
    def __init__(self, stream_id, port, queue_size):
        self.id = stream_id
        self.port = port
        self.collection = collections.deque(maxlen=queue_size)


class SourceStreamConfig:
    def __init__(self, source_id, port, queue_size):
        self.id = source_id
        self.port = port
        self.queue_size = queue_size
