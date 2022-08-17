#!/usr/bin/env python
import json
import logging

from flask import Flask, request, jsonify, make_response, render_template
import logzero
from werkzeug.debug import DebuggedApplication
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

from access_point.conf import AP_WEBSOCKET_PATH, AP_WEBSOCKET_PORT, AP_WEBSOCKET_ADDRESS, AP_WS_EXTERNAL_ADDRESS, LOGGING_LEVEL


app = Flask(__name__, static_url_path='')
app.debug = True


class PubSubAccessPointApplication(WebSocketApplication):

    def __init__(self, ws):
        self.logger = self._setup_logging()
        self.logger.debug('will Init pubsub ws server')
        super(PubSubAccessPointApplication, self).__init__(ws)
        self.logger.debug('Init pubsub ws server')

    def _setup_logging(self):
        log_format = (
            '%(color)s[%(levelname)1.1s %(name)s %(asctime)s:%(msecs)d '
            '%(module)s:%(funcName)s:%(lineno)d]%(end_color)s %(message)s'
        )
        formatter = logzero.LogFormatter(fmt=log_format)
        return logzero.setup_logger(name=self.__class__.__name__, level=logging.getLevelName(LOGGING_LEVEL), formatter=formatter)

    def on_open(self):
        self.logger.debug('New Client connected')

    # def _filter_clients_by_uids_by_event_id(self, event_id, uids):
    #     all_clients = self.ws.handler.server.clients.values()
    #     for client in all_clients:
    #         client_uid = getattr(client, 'uid', None)
    #         client_event_ids = self.get_client_received_events_id(client)
    #         is_valid_client_uid = client_uid and client_uid in uids
    #         is_first_time_receiving_event = event_id not in client_event_ids
    #         if is_valid_client_uid:
    #             self.logger.debug(f'is_first_time_receiving_event: "{is_first_time_receiving_event}" for {event_id}')
    #             if is_first_time_receiving_event:
    #                 yield client

    def on_message(self, message):
        if message is None:
            return
        self.logger.debug('Received a message')

        json_msg = json.loads(message)

        event_data = json.loads(json_msg['event'])
        event_data['status'] = 'received'
        new_json_msg = {'event': json.dumps(event_data)}
        new_msg = json.dumps(new_json_msg)
        self.ws.handler.active_client.ws.send(new_msg)

    #     msg = {
    #         'event': json.dumps({
    #             'action': 'unsubscribe',
    #             'uid': uid,
    #             'subscription': []
    #         })
    #     }
    #     msg_json = json.dumps(msg)
        

        # if 'action' in event_data:
        #     self.handle_action(event_data, message)
        # else:
        #     destinations = event_data.get('destinations', [])
        #     self.send_event_to_subscribers(message, event_data, destinations)

    # def handle_action(self, event_data, message):
    #     self.logger.info(f'handling action: {event_data["action"]}: {event_data}')
    #     action = event_data['action']
    #     if action in ['subscribe', 'unsubscribe']:
    #         current_client = self.ws.handler.active_client
    #         current_client.uid = event_data['uid']
    #         self.send_event_to_internal_services(message)
    #     elif action in ['advertise', 'unadvertise']:
    #         current_client = self.ws.handler.active_client
    #         current_client.uid = event_data['uid']
    #         self.send_event_to_internal_services(message)
    #     elif action == 'annouceInternalClient':
    #         current_client = self.ws.handler.active_client
    #         self.ws.handler.server.internal_client = current_client

    # def get_internal_client(self):
    #     return getattr(self.ws.handler.server, 'internal_client', None)

    # def get_client_received_events_id(self, client):
    #     if not getattr(client, 'received_events_id', None):
    #         client.received_events_id = set()
    #     return client.received_events_id

    # def send_event_to_subscribers(self, message, event_data, destinations):
    #     self.logger.debug(f'sending event to subscribers: {event_data} to {destinations}')
    #     event_id = event_data['id']
    #     for client in self._filter_clients_by_uids_by_event_id(event_id, destinations):
    #         client.ws.send(message)
    #         self.get_client_received_events_id(client).add(event_id)

    # def send_event_to_internal_services(self, message):
    #     self.logger.debug(f'sending event to internal services client: {message}')
    #     self.get_internal_client().ws.send(message)

    # def send_unsubscribe_to_internal_services(self, uid):
    #     msg = {
    #         'event': json.dumps({
    #             'action': 'unsubscribe',
    #             'uid': uid,
    #             'subscription': []
    #         })
    #     }
    #     msg_json = json.dumps(msg)
    #     self.send_event_to_internal_services(msg_json)

    def on_close(self, reason):
        self.logger.info("Connection closed! ")
        # current_client = self.ws.handler.active_client
        # if current_client != self.get_internal_client():
        #     if getattr(current_client, 'uid', None):
        #         self.send_unsubscribe_to_internal_services(current_client.uid)




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
        res['query_id'] = 'blabla123'
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


if __name__ == '__main__':
    WebSocketServer(
        ('0.0.0.0', AP_WEBSOCKET_PORT),
        Resource([
            (f'^{AP_WEBSOCKET_PATH}', PubSubAccessPointApplication),
            ('^/.*', DebuggedApplication(app))
        ]),
        debug=True
    ).serve_forever()
