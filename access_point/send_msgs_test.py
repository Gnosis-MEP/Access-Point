#!/usr/bin/env python
import uuid
import json
from event_service_utils.streams.redis import RedisStreamFactory

from access_point.conf import (
    REDIS_ADDRESS,
    REDIS_PORT,
    SERVICE_STREAM_KEY,
    # LISTEN_EVENT_TYPE_SOME_EVENT_TYPE
)


def make_dict_key_bites(d):
    return {k.encode('utf-8'): v for k, v in d.items()}


def new_msg(event_data):
    event_data.update({'id': str(uuid.uuid4())})
    return {'event': json.dumps(event_data)}



def main():
    stream_factory = RedisStreamFactory(host=REDIS_ADDRESS, port=REDIS_PORT)
    # for checking published events output
    # new_event_type_cmd = stream_factory.create(PUB_EVENT_TYPE_NEW_EVENT_TYPE, stype='streamOnly')

    # for testing sending msgs that the service listens to:
    # import ipdb; ipdb.set_trace()
    # some_event_type_cmd = stream_factory.create(LISTEN_EVENT_TYPE_SOME_EVENT_TYPE, stype='streamOnly')
    # some_event_type_cmd.write_events(
    #     new_msg(
    #         {
    #             'some': 'thing',
    #             'other': 'thing',
    #         }
    #     )
    # )
    # import ipdb; ipdb.set_trace()

    # read published events output
    # events = new_event_type_cmd.read_events()
    # print(list(events))
    # import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    main()
