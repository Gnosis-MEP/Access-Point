import threading

from event_service_utils.logging.decorators import timer_logger
from event_service_utils.services.event_driven import BaseEventDrivenCMDService
from event_service_utils.tracing.jaeger import init_tracer

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

        
        self.reading_stream = self.create_reading_stream(MOCKED_QUERY_ID)

        self.rws_server = rws_server
        self.rws_server.access_point = self

    def create_reading_stream(self, stream_key):
        self.logger.debug(f'creating reading stream: {stream_key}')
        stream = self.stream_factory.create(stream_key)
        return stream

    def send_event_to_publisher_created(self, event_data):
        self.publish_event_type_to_stream('PublisherCreated', event_data)

    def send_event_to_query_received(self, event_data):
        self.publish_event_type_to_stream('QueryReceived', event_data)

    @timer_logger
    def process_data_event(self, event_data, json_msg):
        if not super(AccessPoint, self).process_data_event(event_data, json_msg):
            return False
        # do something here
        pass

    def process_event_type(self, event_type, event_data, json_msg):
        if not super(AccessPoint, self).process_event_type(event_type, event_data, json_msg):
            return False
        if event_type == 'SomeEventType':
            # do some processing
            pass
        elif event_type == 'OtherEventType':
            # do some other processing
            pass
    
    def process_data(self):
        # if MOCKED_QUERY_ID in self.rws_server.query_id_to_ws_client_map.keys():
        #     query_id = MOCKED_QUERY_ID
        #     self.query_id_streams_map[query_id] = self.reading_stream
        if not self.reading_stream:
            time.sleep(0.01)
            return
        event_list = self.reading_stream.read_events(count=1)
        for event_tuple in event_list:
            event_id, json_msg = event_tuple
            try:
                if MOCKED_QUERY_ID in self.rws_server.query_id_to_ws_client_map.keys():
                    query_id = MOCKED_QUERY_ID
                    self.rws_server.send_msg_to_ws_client(query_id, json_msg)
                else:
                    event_type = MOCKED_QUERY_ID
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
