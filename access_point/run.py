#!/usr/bin/env python
from event_service_utils.streams.redis import RedisStreamFactory

from access_point.service import AccessPoint

from flask import Flask, request, jsonify, make_response, render_template
from werkzeug.debug import DebuggedApplication

from ws_server import RedisWebSocketServer, PubSubAccessPointApplication
from geventwebsocket import Resource

from access_point.conf import (
    AP_WEBSOCKET_PATH,
    AP_WEBSOCKET_PORT,
    AP_WEBSOCKET_ADDRESS,
    AP_WS_EXTERNAL_ADDRESS,
    REDIS_ADDRESS,
    REDIS_PORT,
    PUB_EVENT_LIST,
    SERVICE_STREAM_KEY,
    SERVICE_CMD_KEY_LIST,
    LOGGING_LEVEL,
    TRACER_REPORTING_HOST,
    TRACER_REPORTING_PORT,
    SERVICE_DETAILS,
)

app = Flask(__name__, static_url_path='')
app.debug = True

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/publisher/registration", methods=['get', 'post'])
def publisher_registration():
    if request.method == 'GET':
        context = {
           'AP_WS_EXTERNAL_ADDRESS': AP_WS_EXTERNAL_ADDRESS,
           'AP_WEBSOCKET_ADDRESS': AP_WEBSOCKET_ADDRESS,
           'AP_WEBSOCKET_PORT': AP_WEBSOCKET_PORT,
           'AP_WEBSOCKET_PATH': AP_WEBSOCKET_PATH
        }
        return render_template('create_publisher.html', **context)
    else:
        return make_response(jsonify(request.json), 200)

@app.route("/subscriber/registration", methods=['get'])
def subscriber_registration():
    context = {
        'AP_WS_EXTERNAL_ADDRESS': AP_WS_EXTERNAL_ADDRESS,
        'AP_WEBSOCKET_ADDRESS': AP_WEBSOCKET_ADDRESS,
        'AP_WEBSOCKET_PORT': AP_WEBSOCKET_PORT,
        'AP_WEBSOCKET_PATH': AP_WEBSOCKET_PATH
    }
    return render_template('create_subscriber.html', **context)

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


def run_service():
    tracer_configs = {
        'reporting_host': TRACER_REPORTING_HOST,
        'reporting_port': TRACER_REPORTING_PORT,
    }
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
    service = AccessPoint(
        service_stream_key=SERVICE_STREAM_KEY,
        service_cmd_key_list=SERVICE_CMD_KEY_LIST,
        pub_event_list=PUB_EVENT_LIST,
        service_details=SERVICE_DETAILS,
        rws_server=ws,
        stream_factory=stream_factory,
        logging_level=LOGGING_LEVEL,
        tracer_configs=tracer_configs
    )
    service.run()


def main():
    try:
        run_service()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
