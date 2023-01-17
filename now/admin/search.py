import requests
from docarray import Document
from jina import Client

API_KEY = 'my_key'

url = f"https://nowrun.jina.ai/api/v1/search-app/search"
host = 'grpcs://nowapi-c74eae8ebe.wolf.jina.ai'
url = 'http://localhost:8080/api/v1/search-app/search'
host = 'grpc://0.0.0.0'
port = 9090
direct = False


if direct:
    # directly requesting the jina gateway
    result = Client(host=host).post(
        '/search',
        Document(chunks=Document(text='girl on motorbike')),
        {'api_key': API_KEY},
    )
    for match in result[0].matches:
        print(match.tags['uri'])
else:
    # request the bff
    request_body = {
        'host': host,
        'port': port,
        'api_key': API_KEY,
        'fields': {'index_field_name': {'text': 'girl on motorbike'}},
    }

    response = requests.post(
        url,
        json=request_body,
    )


if 'message' in response.json():
    print(response.json()['message'])
