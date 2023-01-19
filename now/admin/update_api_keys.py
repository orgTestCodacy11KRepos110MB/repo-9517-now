import uuid

import requests

from now.admin.utils import get_default_request_body

#  TODO needs to be updated to work on cli / or even putting things like this into a new client package


def update_api_keys(api_keys, remote_host):
    if not isinstance(api_keys, list):
        api_keys = [api_keys]

    url = f"https://nowrun.jina.ai/api/v1"  # remote
    # url = f'http://localhost:8080/api/v1'  # for local testing
    request_body = get_default_request_body(secured=True, host=remote_host)
    # request_body['host'] = f'grpc://0.0.0.0'  # for local testing
    # request_body['port'] = 9090  # for local testing
    request_body['api_keys'] = api_keys
    response = requests.post(
        f'{url}/admin/updateApiKeys',
        json=request_body,
    )


if __name__ == '__main__':
    api_key = str(uuid.uuid4())
    for i in range(100):  # increase the probability that all replicas get the new key
        update_api_keys(
            api_keys=[api_key],
            remote_host='grpc://0.0.0.0',
        )
        print(api_key)
