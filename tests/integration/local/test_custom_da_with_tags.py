import pytest
import requests
from jina import Client
from tests.integration.local.conftest import (  # noqa
    SEARCH_URL,
    get_flow,
    get_request_body,
)

from now.constants import ACCESS_PATHS, Models


@pytest.mark.parametrize(
    'get_flow',
    [
        (
            {},
            {
                'user_input_dict': {
                    'filter_fields': ['color'],
                },
                'document_mappings': [[Models.CLIP_MODEL, 512, ['text_field']]],
            },
        )
    ],
    indirect=True,
)
def test_search_filters(
    get_flow, data_with_tags, setup_service_running, random_index_name
):
    client = Client(host='http://localhost:8081')
    client.index(
        data_with_tags,
        parameters={
            'access_paths': ACCESS_PATHS,
        },
    )
    request_body = get_request_body(secured=False)
    request_body['query'] = [{'name': 'text', 'value': 'test', 'modality': 'text'}]
    request_body['filters'] = {'color': 'Blue Color'}
    response = requests.post(
        SEARCH_URL,
        json=request_body,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['tags']['color'] == 'Blue Color'
