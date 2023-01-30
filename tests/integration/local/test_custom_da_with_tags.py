import requests
from tests.integration.local.conftest import SEARCH_URL, get_flow, get_request_body
from tests.integration.local.data import data_with_tags

from now.constants import ACCESS_PATHS, Models


def test_search_filters(
    data_with_tags, setup_service_running, random_index_name, tmpdir
):
    f = get_flow(
        tmpdir=tmpdir,
        indexer_args={
            'index_name': random_index_name,
            'user_input_dict': {
                'filter_fields': ['color'],
            },
            'document_mappings': [[Models.CLIP_MODEL, 512, ['title']]],
        },
    )
    with f:
        f.index(
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
