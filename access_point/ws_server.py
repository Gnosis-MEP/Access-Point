#!/usr/bin/env python
import json
import logging
import time
import threading
import uuid

import logzero
from geventwebsocket import WebSocketServer, WebSocketApplication

from access_point.conf import (
    LOGGING_LEVEL,
)

MOCKED_QUERY_ID = '91b0e93c4b24aaa6fb37ce0e5e216c94'

class RedisWebSocketServer(WebSocketServer):
    """
    This is the main class responsible for the websocket server.
    It should talk to redis through the AccessPoint server class instance.
    """

    def __init__(self, *args, **kwargs):
        self.stream_factory = kwargs.pop('stream_factory', None)
        self.service_stream = None
        self.query_id_to_ws_client_map = {}
        self.query_id_streams_map = {}
        self.access_point = None
        super(RedisWebSocketServer, self).__init__(*args, **kwargs)

    def _mocked_register_pub(self):
        event_data = {
            'id': f'AccessPoint:{str(uuid.uuid4())}',
            "publisher_id": "Publisher1",
            # "source": "rtmp://172.17.0.1/live/mystream",
            "source": "rtmp://host.docker.internal/vod2/cars.mp4",
            "meta": {
                "color": "True",
                "fps": "30",
                "resolution": "300x300"
            }
        }
        self.access_point.send_event_to_publisher_created(event_data)

    def _mocked_register_query(self):
        query_text = "REGISTER QUERY AnyPersonFromPub1LatencyMin OUTPUT K_GRAPH_JSON CONTENT ObjectDetection MATCH (p:person) FROM Publisher1 WITHIN TUMBLING_COUNT_WINDOW(1) WITH_QOS latency = 'min' RETURN *"
        event_data = {
            'id': f'AccessPoint:{str(uuid.uuid4())}',
            'subscriber_id': 'Subscriber1',
            'query': query_text
        }
        self.access_point.send_event_to_query_received(event_data)

    def serve_forever(self, stop_timeout=None):
        """
        this is the main entrypoint in the WS server.
        For now it is only adding the mocked pub/query msgs and then spawning a thread that will read a query output stream
        (using the MOCKED_QUERY_ID).
        """
        # if self.stream_factory:
        #     # self._mocked_register_pub_and_query()
        #     self.redis_thread = threading.Thread(target=self.forever_read_redis_stream, args=(MOCKED_QUERY_ID,))
        #     self.redis_thread.start()
        super(RedisWebSocketServer, self).serve_forever(stop_timeout=stop_timeout)
        # if self.stream_factory:
        #     self.redis_thread.join()

    def redis_default_event_deserializer(self, json_msg):
        event_key = b'event' if b'event' in json_msg else 'event'
        event_json = json_msg.get(event_key, '{}')
        event_data = json.loads(event_json)
        return event_data

    def send_msg_to_ws_client(self, query_id, json_msg):
        "method used to send msgs to a WS client, based on the query_id this msg is related to"
        client = self.query_id_to_ws_client_map.get(query_id)
        utf8_decoded_json_msg = json_msg
        if b'event' in json_msg:
            utf8_decoded_json_msg = {
                'event': json_msg[b'event'].decode('utf-8')
            }
        if client is None:
            self.logger.warning(f'No client mapped for query_id: {query_id}. Will ignore message: {json_msg}')
            return
        self.logger.debug(f'Sending msg to {query_id} WS client: {utf8_decoded_json_msg}')
        client.ws.send(json.dumps(utf8_decoded_json_msg))

    def process_event_type(self, event_type, json_msg):
        "method used to process any event type in this server, eg: QueryCreated"
        event_data = self.redis_default_event_deserializer(json_msg)
        self.logger.debug(f'read this event of type {event_type}, and will process it: {event_data}')
        if event_type == 'QueryCreated': # replace with const from conf.py
            # i need to identify the responsible active client to send to
            # i need to send query_id to the client here
            pass

    def forever_read_redis_stream(self, stream_key):
        """
        method that will run forever, and read a given redis stream (using the strem key arg).
        then it process any read msg accordinly. Eg: send to WS if it is reading from the query output stream, or process the event
        if receiving a event type of QueryCreated from Genosis, for example.
        """
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
    """
    This class is responsible only for stuff related to the client(browser) ws communication.
    Most specifically, it is responsible for handling the msgs that arrive from the WS client (ex: RegisterWSConnectionForQuery)
    Any communication with redis, or routing of msgs from redis to WS should <NOT> be done in this class.
    """
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
        "method that is caleld when a WS connection is openned"
        self.logger.debug('New Client connected')

    def on_message(self, message):
        "method that is called every time a ws msg is received by the server"
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
        elif event_type == 'RegisterWSConnectionForPublisher':
            publisher_id = event_data['publisher_id']
            self.ws.handler.server._mocked_register_pub()
            self.ws.handler.active_client.ws.send('Publisher Registered')
        elif event_type == 'RegisterQuery':
            self.ws.handler.server._mocked_register_query()
            self.ws.handler.active_client.ws.send(MOCKED_QUERY_ID) # this should be received from redis then sent to the client

            # you will need to bind a query id generated from the ws client in order to send the query id generated by gnosis to the client


    def on_close(self, reason):
        "method that is caleld when a WS connection is closed"
        self.logger.info("Connection closed! ")
        current_client = self.ws.handler.active_client
        # if getattr(current_client, 'uid', None):
        #     self.send_unsubscribe_to_internal_services(current_client.uid)



