import threading

from event_service_utils.logging.decorators import timer_logger
from event_service_utils.services.event_driven import BaseEventDrivenCMDService
from event_service_utils.tracing.jaeger import init_tracer

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

        self.rws_server = rws_server
        self.rws_server.access_point = self

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
