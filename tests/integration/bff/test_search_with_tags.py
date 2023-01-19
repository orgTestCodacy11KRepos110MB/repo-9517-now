import requests
from tests.integration.bff.conftest import HOST, PORT, SEARCH_URL, get_flow, index_data

from now.admin.utils import get_default_request_body


def get_request_body():
    request_body = get_default_request_body('local', False, None)
    request_body['host'] = HOST
    request_body['port'] = PORT
    return request_body


def test_search_filters(setup_service_running, random_index_name, tmpdir):
    f = get_flow(
        tmpdir=tmpdir,
        indexer_args={
            'index_name': random_index_name,
            'user_input_dict': {
                'filter_fields': ['color'],
            },
        },
    )
    with f:
        index_data(f)
        request_body = get_request_body()
        request_body['query'] = [{'name': 'text', 'value': 'test', 'modality': 'text'}]
        request_body['filters'] = {'color': 'Blue Color'}
        response = requests.post(
            SEARCH_URL,
            json=request_body,
        )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['tags']['color'] == 'Blue Color'
