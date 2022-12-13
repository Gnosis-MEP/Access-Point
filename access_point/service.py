import threading

from event_service_utils.logging.decorators import timer_logger
from event_service_utils.services.event_driven import BaseEventDrivenCMDService
from event_service_utils.tracing.jaeger import init_tracer
import uuid

from access_point.conf import (
    LISTEN_EVENT_TYPE_QUERY_CREATED,
    LISTEN_EVENT_TYPE_PUBLISHER_CREATED,
    PUB_EVENT_TYPE_QUERY_RECEIVED,
    PUB_EVENT_TYPE_PUBLISHER_CREATED
)

from ws_server import MOCKED_QUERY_ID

import time


class AccessPoint(BaseEventDrivenCMDService):
    def __init__(self,
                 service_stream_key, service_cmd_key_list,
                 pub_event_list, service_details,
                 rws_server,
                 stream_factory,
                 logging_level,
                 tracer_configs):
        tracer = init_tracer(self.__class__.__name__, **tracer_configs)
        super(AccessPoint, self).__init__(
            name=self.__class__.__name__,
            service_stream_key=service_stream_key,
            service_cmd_key_list=service_cmd_key_list,
            pub_event_list=pub_event_list,
            service_details=service_details,
            stream_factory=stream_factory,
            logging_level=logging_level,
            tracer=tracer,
        )
        self.cmd_validation_fields = ['id']
        self.data_validation_fields = ['id']

        self.client_registration_ack_map = {}
        self.query_stream_map = {}

        self.rws_server = rws_server
        self.rws_server.access_point = self

    def publish_publisher_created_event(self, event_data, active_client):
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
        self.publish_event_type_to_stream(PUB_EVENT_TYPE_PUBLISHER_CREATED, event_data)
        self.client_registration_ack_map.update({event_data['id']: active_client})
        active_client.ws.send('Publisher Registered')

    def publish_query_received_event(self, event_data, active_client):
        query_text = "REGISTER QUERY AnyPersonFromPub1LatencyMin OUTPUT K_GRAPH_JSON CONTENT ObjectDetection MATCH (p:person) FROM Publisher1 WITHIN TUMBLING_COUNT_WINDOW(1) WITH_QOS latency = 'min' RETURN *"
        event_data = {
            'id': f'AccessPoint:{str(uuid.uuid4())}',
            'subscriber_id': 'Subscriber1',
            'query': query_text
        }
        self.publish_event_type_to_stream(PUB_EVENT_TYPE_QUERY_RECEIVED, event_data)
        self.client_registration_ack_map.update({event_data['id']: active_client})
        active_client.ws.send(MOCKED_QUERY_ID)

    @timer_logger
    def process_data_event(self, event_data, json_msg):
        if not super(AccessPoint, self).process_data_event(event_data, json_msg):
            return False
        # do something here
        pass

    def process_event_type(self, event_type, event_data, json_msg):
        if not super(AccessPoint, self).process_event_type(event_type, event_data, json_msg):
            return False
        if event_type == LISTEN_EVENT_TYPE_QUERY_CREATED:
            # inform client that of the query id
            # query_id = event_data['query_id']
            # registration_id = event_data['registration_id']
            # if registration_id in self.client_registration_ack_map.keys():
            #     registration_client = self.client_registration_ack_map[registration_id]
            #     registration_client.ws.send(query_id)
            # create reading stream for query and add to map
            self.logger.debug(f'creating query stream: {query_id}')
            query_stream = self.stream_factory.create(query_id)
            self.query_stream_map.update({query_id: query_stream})
        elif event_type == LISTEN_EVENT_TYPE_PUBLISHER_CREATED:
            # get rquestid
            # check if id is in self.rws_server.request_id_to_ws_client_map
            # inform client that the publisher has been registered
            pass
    
    def process_data(self):
        """
        method that will run forever, and read a given redis stream.
        then it process any read msg accordinly. Eg: send to WS if it is reading from the query output stream, or process the event
        if receiving a event type of QueryCreated from Genosis, for example.
        """
        
        query_stream_keys = list(self.query_stream_map.keys())
        for query_stream_key in query_stream_keys:
            query_stream = self.query_stream_map.get(query_stream_key)

            if not query_stream:
                time.sleep(0.01)
                return
            event_list = query_stream.read_events(count=1)
            for event_tuple in event_list:
                event_id, json_msg = event_tuple
                try:
                    if query_stream_key in self.rws_server.query_id_to_ws_client_map.keys():
                        query_id = query_stream_key
                        self.rws_server.send_msg_to_ws_client(query_id, json_msg)
                    else:
                        event_type = query_stream_key
                        event_data = self.default_event_deserializer(json_msg)
                        self.process_event_type(event_type, event_data, json_msg)
                        # self.process_data_event_wrapper(event_data, json_msg)
                except Exception as e:
                    self.logger.error(f'Error processing {json_msg}:')
                    self.logger.exception(e)
                finally:
                    pass
                    # if self.ack_data_stream_events:
                        # we are always ack the events, even if they fail.
                        # in a better world we would actually do some treatments to
                        # see if the event should be re-processed or not, before ack.
                        # self.service_stream.ack(event_id)

    def log_state(self):
        super(AccessPoint, self).log_state()
        self.logger.info(f'Service name: {self.name}')
        # function for simple logging of python dictionary  
        # self._log_dict('Some Dictionary', self.some_dict)
        self._log_dict('Consumer groups', self.service_cmd_cg_stream_map)

    def run(self):
        super(AccessPoint, self).run()
        self.log_state()
        self.cmd_thread = threading.Thread(target=self.run_forever, args=(self.process_cmd,))
        self.data_thread = threading.Thread(target=self.run_forever, args=(self.process_data,))
        self.cmd_thread.start()
        self.data_thread.start()
        self.rws_server.serve_forever()
        self.cmd_thread.join()
        self.data_thread.join()
