import collections

from marshmallow import Schema, fields


class StreamSchema(Schema):
    id = fields.Int()


class Stream:
    def __init__(self, stream_id, port, queue_size):
        self.id = stream_id
        self.port = port
        self.collection = collections.deque(maxlen=queue_size)


class ServerConfig:
    def __init__(self, port, source_streams):
        self.port = port
        self.model_dir = None
        self.label_dir = None
        self.source_streams: list[SourceStreamConfig] = source_streams


class SourceStreamConfig:
    def __init__(self, source_id, port, queue_size):
        self.id = source_id
        self.port = port
        self.queue_size = queue_size


class ModelConfig:
    def __init__(self, base_url, name, date):
        self.base_url = base_url
        self.name = name
        self.date = date


class LabelConfig:
    def __init__(self, base_url, name):
        self.base_url = base_url
        self.name = name
