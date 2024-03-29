from multiprocessing import Process
from time import sleep

import hubble
import requests
from docarray import Document
from jina import Flow
from tests.integration.test_end_to_end import assert_search

from deployment.bff.app.app import run_server
from now.admin.utils import get_default_request_body
from now.constants import (
    ACCESS_PATHS,
    EXTERNAL_CLIP_HOST,
    NOW_PREPROCESSOR_VERSION,
    NOW_QDRANT_INDEXER_VERSION,
)
from now.executor.name_to_id_map import name_to_id_map
from now.now_dataclasses import UserInput

API_KEY = 'my_key'
base_url = 'http://localhost:8080/api/v1'
search_url = f'{base_url}/image-or-text-to-image-or-text/search'
update_api_keys_url = f'{base_url}/admin/updateApiKeys'
update_emails_url = f'{base_url}/admin/updateUserEmails'
host = 'grpc://0.0.0.0'
port = 9090


def get_request_body():
    request_body = get_default_request_body('local', True, None)
    request_body['host'] = 'grpc://0.0.0.0'
    request_body['port'] = 9089
    return request_body


def get_flow():
    client = hubble.Client(
        token=get_request_body()['jwt']['token'], max_retries=None, jsonify=True
    )
    admin_email = client.get_user_info()['data'].get('email')
    f = (
        Flow(port_expose=9089)
        .add(
            uses=f'jinahub+docker://{name_to_id_map.get("NOWPreprocessor")}/{NOW_PREPROCESSOR_VERSION}',
            uses_with={'app': 'image_text_retrieval', 'admin_emails': [admin_email]},
        )
        .add(
            host=EXTERNAL_CLIP_HOST,
            port=443,
            tls=True,
            external=True,
        )
        .add(
            uses=f'jinahub+docker://{name_to_id_map.get("NOWQdrantIndexer16")}/{NOW_QDRANT_INDEXER_VERSION}',
            uses_with={'dim': 512, 'admin_emails': [admin_email]},
        )
    )
    return f


def index(f):
    f.index(
        [Document(text='test') for i in range(10)],
        parameters={
            'jwt': get_request_body()['jwt'],
            'user_input': UserInput().__dict__,
            'access_paths': ACCESS_PATHS,
        },
    )


def start_bff(port=8080, daemon=True):
    p1 = Process(target=run_server, args=(port,))
    p1.daemon = daemon
    p1.start()


def test_add_key():
    f = get_flow()
    with f:
        index(f)
        start_bff()
        sleep(5)

        request_body = get_request_body()
        print('# Test adding user email')
        request_body['user_emails'] = ['florian.hoenicke@jina.ai']
        response = requests.post(
            update_emails_url,
            json=request_body,
        )
        assert response.status_code == 200

        print('# test api keys')
        print('# search with invalid api key')
        request_body = get_request_body()
        request_body['text'] = 'girl on motorbike'
        del request_body['jwt']
        request_body['api_key'] = API_KEY
        request_body['limit'] = 9
        assert_search(search_url, request_body, expected_status_code=500)
        print('# add api key')
        request_body_update_keys = get_request_body()
        request_body_update_keys['api_keys'] = [API_KEY]
        response = requests.post(
            update_api_keys_url,
            json=request_body_update_keys,
        )
        if response.status_code != 200:
            print(response.text)
            print(response.json()['message'])
            raise Exception(f'Response status is {response.status_code}')
        print('# the same search should work now')
        assert_search(search_url, request_body)
