#!/usr/bin/env python
import json
import logging
import time
import threading
import uuid

from flask import Flask, request, jsonify, make_response, render_template
import logzero
from werkzeug.debug import DebuggedApplication
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

from event_service_utils.streams.redis import RedisStreamFactory

from access_point.conf import (
    AP_WEBSOCKET_PATH,
    AP_WEBSOCKET_PORT,
    AP_WEBSOCKET_ADDRESS,
    AP_WS_EXTERNAL_ADDRESS,
    REDIS_ADDRESS,
    REDIS_PORT,
    SERVICE_STREAM_KEY,
    LOGGING_LEVEL
)

MOCKED_QUERY_ID = '91b0e93c4b24aaa6fb37ce0e5e216c94'


app = Flask(__name__, static_url_path='')
app.debug = True

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/publisher/registration", methods=['get', 'post'])
def publisher_registration():
    if request.method == 'GET':
        return render_template('create_publisher.html')
    else:
        return make_response(jsonify(request.json), 200)

@app.route("/subscriber/registration", methods=['get', 'post'])
def subscriber_registration():
    if request.method == "GET":
        return render_template('create_subscriber.html')
    else:
        res = {}
        res['query_id'] = MOCKED_QUERY_ID
        return make_response(jsonify(res), 200)

@app.route("/subscribe/query/<string:query_id>", methods=['get'])
def query_detail(query_id):
    context = {
        'query_id': query_id,
        'AP_WS_EXTERNAL_ADDRESS': AP_WS_EXTERNAL_ADDRESS,
        'AP_WEBSOCKET_ADDRESS': AP_WEBSOCKET_ADDRESS,
        'AP_WEBSOCKET_PORT': AP_WEBSOCKET_PORT,
        'AP_WEBSOCKET_PATH': AP_WEBSOCKET_PATH
    }
    return render_template('subscriber/query_detail.html', **context)


class RedisWebSocketServer(WebSocketServer):

    def __init__(self, *args, **kwargs):
        self.stream_factory = kwargs.pop('stream_factory', None)
        self.service_stream = None
        self.query_id_to_ws_client_map = {}
        self.query_id_streams_map = {}
        super(RedisWebSocketServer, self).__init__(*args, **kwargs)

    def _mocked_register_pub_and_query(self):
        event_data = {
            'id': f'AccessPoint:{str(uuid.uuid4())}',
            "publisher_id": "Publisher1",
            "source": "rtmp://172.17.0.1/live/mystream",
            "meta": {
                "color": "True",
                "fps": "10",
                "resolution": "300x300"
            }
        }
        self.send_msg_to_stream('PublisherCreated', event_data)

        time.sleep(1)
        query_text = "REGISTER QUERY AnyPersonFromPub1LatencyMin OUTPUT K_GRAPH_JSON CONTENT ObjectDetection MATCH (p:person) FROM Publisher1 WITHIN TUMBLING_COUNT_WINDOW(1) WITH_QOS latency = 'min' RETURN *"
        event_data = {
            'id': f'AccessPoint:{str(uuid.uuid4())}',
            'subscriber_id': 'Subscriber1',
            'query': query_text
        }
        self.send_msg_to_stream('QueryReceived', event_data)

    def serve_forever(self, stop_timeout=None):
        if self.stream_factory:
            self._mocked_register_pub_and_query()
            self.redis_thread = threading.Thread(target=self.forever_read_redis_stream, args=(MOCKED_QUERY_ID,))
            self.redis_thread.start()
        super(RedisWebSocketServer, self).serve_forever(stop_timeout=stop_timeout)
        if self.stream_factory:
            self.redis_thread.join()

    def redis_default_event_deserializer(self, json_msg):
        event_key = b'event' if b'event' in json_msg else 'event'
        event_json = json_msg.get(event_key, '{}')
        event_data = json.loads(event_json)
        return event_data

    def redis_default_event_serializer(self, event_data):
        event_msg = {'event': json.dumps(event_data)}
        return event_msg

    def send_msg_to_stream(self, destination_stream_key, event_data):
        if self.stream_factory is None:
            return
        destination_stream = self.stream_factory.create(destination_stream_key, stype='streamOnly')
        return destination_stream.write_events(self.redis_default_event_serializer(event_data))

    def send_msg_to_ws_client(self, query_id, json_msg):
        client = self.query_id_to_ws_client_map.get(query_id)
        utf8_encoded_json_msg = json_msg
        if b'event' in json_msg:
            utf8_encoded_json_msg = {
                'event': json_msg[b'event'].decode('utf-8')
            }
        if client is None:
            self.logger.warning(f'No client mapped for query_id: {query_id}. Will ignore message: {json_msg}')
            return
        self.logger.debug(f'Sending msg to {query_id} WS client: {utf8_encoded_json_msg}')
        client.ws.send(json.dumps(utf8_encoded_json_msg))

    def process_event_type(self, event_type, json_msg):
        event_data = self.redis_default_event_deserializer(json_msg)
        self.logger.debug(f'read this event of type {event_type}, and will process it: {event_data}')
        if event_type == 'QueryCreated': # replace with const from conf.py
            pass

    def forever_read_redis_stream(self, stream_key):
        self.logger.debug(f'created reading stream: {stream_key}')
        stream = self.stream_factory.create(stream_key)
        if stream_key in self.query_id_to_ws_client_map.keys():
            query_id = stream_key
            self.query_id_streams_map[query_id] = stream
        self.logger.debug('will read it forever')
        while True:
            if not stream:
                time.sleep(0.01)
                continue

            event_list = stream.read_events(count=1)
            for event_tuple in event_list:
                event_id, json_msg = event_tuple
                try:
                    if stream_key in self.query_id_to_ws_client_map.keys():
                        query_id = stream_key
                        self.send_msg_to_ws_client(query_id, json_msg)
                    else:
                        event_type = stream_key
                        self.process_event_type(event_type, json_msg)
                except Exception as e:
                    self.logger.error(f'Error processing {json_msg}:')
                    self.logger.exception(e)
                finally:
                    pass
                    # stream.ack(event_id)
                    # no ack for now, later may change to: we are always ack the events, even if they fail.


class PubSubAccessPointApplication(WebSocketApplication):
    def __init__(self, ws):
        self.logger = self._setup_logging()
        super(PubSubAccessPointApplication, self).__init__(ws)

    def _setup_logging(self):
        log_format = (
            '%(color)s[%(levelname)1.1s %(name)s %(asctime)s:%(msecs)d '
            '%(module)s:%(funcName)s:%(lineno)d]%(end_color)s %(message)s'
        )
        formatter = logzero.LogFormatter(fmt=log_format)
        return logzero.setup_logger(name=self.__class__.__name__, level=logging.getLevelName(LOGGING_LEVEL), formatter=formatter)

    def on_open(self):
        self.logger.debug('New Client connected')

    def on_message(self, message):
        if message is None:
            return
        self.logger.debug('Received a message')

        json_msg = json.loads(message)

        event_type = json_msg.get('event_type', None)

        event_data = json.loads(json_msg['event'])
        self.process_event_type(event_type, event_data, message)

    def process_event_type(self, event_type, event_data, message):
        self.logger.info(f'handling event type "{event_type}": {event_data}')
        if event_type == 'RegisterWSConnectionForQuery':
            query_id = event_data['query_id']
            current_client = self.ws.handler.active_client
            current_client.uid = query_id
            self.ws.handler.server.query_id_to_ws_client_map[query_id] = current_client

    def on_close(self, reason):
        self.logger.info("Connection closed! ")
        current_client = self.ws.handler.active_client
        # if getattr(current_client, 'uid', None):
        #     self.send_unsubscribe_to_internal_services(current_client.uid)







if __name__ == '__main__':
    stream_factory = RedisStreamFactory(host=REDIS_ADDRESS, port=REDIS_PORT)
    ws = RedisWebSocketServer(
        ('0.0.0.0', AP_WEBSOCKET_PORT),
        Resource([
            (f'^{AP_WEBSOCKET_PATH}', PubSubAccessPointApplication),
            ('^/.*', DebuggedApplication(app))
        ]),
        stream_factory=stream_factory,
        debug=True,
    )
    ws.serve_forever()

