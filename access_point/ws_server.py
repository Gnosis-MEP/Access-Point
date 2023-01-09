import json
import logging

import logzero
from geventwebsocket import WebSocketServer, WebSocketApplication

from access_point.conf import (
    LOGGING_LEVEL,
)

class RedisWebSocketServer(WebSocketServer):
    """
    This is the main class responsible for the websocket server.
    It should talk to redis through the AccessPoint server class instance.
    """

    def __init__(self, *args, **kwargs):
        self.query_id_to_ws_client_map = {}
        self.query_id_streams_map = {}
        self.access_point = None
        super(RedisWebSocketServer, self).__init__(*args, **kwargs)

    def serve_forever(self, stop_timeout=None):
        """
        this is the main entrypoint in the WS server.
        """
        super(RedisWebSocketServer, self).serve_forever(stop_timeout=stop_timeout)

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
        # self.logger.debug(f'Sending msg to {query_id} WS client: {utf8_decoded_json_msg}')
        client.ws.send(json.dumps(utf8_decoded_json_msg))


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
            self.ws.handler.server.access_point.\
                publish_publisher_created_event(event_data, self.ws.handler.active_client)
        elif event_type == 'RegisterQuery':
            self.ws.handler.server.access_point.\
                publish_query_received_event(event_data, self.ws.handler.active_client)


    def on_close(self, reason):
        "method that is caleld when a WS connection is closed"
        self.logger.info("Connection closed! ")
        current_client = self.ws.handler.active_client
        # if getattr(current_client, 'uid', None):
        #     self.send_unsubscribe_to_internal_services(current_client.uid)



