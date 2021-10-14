import collections

from marshmallow import Schema, fields


class StreamSchema(Schema):
    source_id = fields.Int()


class Stream:
    def __init__(self, source_id, source_port):
        self.source_id = source_id
        self.source_port = source_port
        self.collection = collections.deque(maxlen=5)