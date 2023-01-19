import os

import hubble


def get_default_request_body(host, secured):
    request_body = {'host': host}
    if secured:
        if 'WOLF_TOKEN' in os.environ:
            os.environ['JINA_AUTH_TOKEN'] = os.environ['WOLF_TOKEN']
        request_body['jwt'] = {'token': hubble.get_token()}
    return request_body
