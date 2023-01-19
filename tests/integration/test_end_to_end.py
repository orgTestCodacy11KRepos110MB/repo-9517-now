import base64
import json
import os
from argparse import Namespace

import pytest
import requests
from docarray import DocumentArray

from now.admin.utils import get_default_request_body
from now.cli import cli
from now.constants import DatasetTypes
from now.demo_data import DemoDatasetNames
from now.deployment.deployment import list_all_wolf


@pytest.fixture
def test_search_image(resources_folder_path: str):
    with open(os.path.join(resources_folder_path, 'image', 'a.jpg'), 'rb') as f:
        binary = f.read()
        img_query = base64.b64encode(binary).decode('utf-8')
    return img_query


def test_token_exists():
    list_all_wolf()


@pytest.mark.parametrize(
    'query_fields, index_fields, filter_fields, dataset',
    [
        (
            'image',
            ['image'],
            ['label'],
            DemoDatasetNames.BIRD_SPECIES,
        ),
        (
            'text',
            ['lyrics'],
            [],
            DemoDatasetNames.POP_LYRICS,
        ),
        (
            'text',
            ['video', 'description'],
            [],
            DemoDatasetNames.TUMBLR_GIFS_10K,
        ),
        (
            'text',
            ['image'],
            ['label'],
            DemoDatasetNames.BEST_ARTWORKS,
        ),
    ],
)
@pytest.mark.timeout(60 * 10)
def test_end_to_end(
    cleanup,
    start_bff,
    start_playground,
    query_fields,
    index_fields,
    filter_fields,
    dataset,
    test_search_image,
):
    kwargs = {
        'now': 'start',
        'flow_name': 'nowapi',
        'dataset_type': DatasetTypes.DEMO,
        'admin_name': 'team-now',
        'index_fields': index_fields,
        'filter_fields': filter_fields,
        'dataset_name': dataset,
        'secured': True,
        'api_key': None,
        'additional_user': False,
        'proceed': True,
    }
    kwargs = Namespace(**kwargs)
    response = cli(args=kwargs)
    # Dump the flow details from response host to a tmp file
    flow_details = {'host': response['host']}
    with open(f'{cleanup}/flow_details.json', 'w') as f:
        json.dump(flow_details, f)

    assert_deployment_response(response)
    assert_deployment_queries(
        dataset=dataset,
        query_fields=query_fields,
        kwargs=kwargs,
        test_search_image=test_search_image,
        response=response,
    )
    if query_fields == 'text':
        host = response.get('host')
        request_body = get_search_request_body(
            dataset=dataset,
            kwargs=kwargs,
            test_search_image=test_search_image,
            host=host,
            search_modality='text',
        )
        suggest_url = f'http://localhost:8080/api/v1/search-app/suggestion'
        assert_suggest(suggest_url, request_body)


def assert_search(search_url, request_body, expected_status_code=200):
    response = requests.post(
        search_url,
        json=request_body,
    )
    assert response.status_code == expected_status_code, (
        f"Received code {response.status_code} but {expected_status_code} was expected. \n"
        f"text: {json.dumps(response.json(), indent=2)}"
    )
    if response.status_code == 200:
        assert len(response.json()) == 9


def assert_suggest(suggest_url, request_body):
    old_request_text = request_body.pop('query')
    request_body['text'] = old_request_text[0]['value']
    response = requests.post(
        suggest_url,
        json=request_body,
    )
    assert (
        response.status_code == 200
    ), f"Received code {response.status_code} with text: {response.json()['message']}"
    docs = DocumentArray.from_json(response.content)
    assert 'suggestions' in docs[0].tags, f'No suggestions found in {docs[0].tags}'
    assert docs[0].tags['suggestions'] == [old_request_text[0]['value']], (
        f"Expected suggestions to be {old_request_text[0]['value']} but got "
        f"{docs[0].tags['suggestions']}"
    )


def assert_deployment_queries(
    dataset,
    query_fields,
    kwargs,
    test_search_image,
    response,
):
    port = response.get('bff_port') if os.environ.get('NOW_TESTING', False) else '8080'
    url = f'http://localhost:{port}/api/v1'
    host = response.get('host')
    # normal case
    request_body = get_search_request_body(
        dataset=dataset,
        kwargs=kwargs,
        test_search_image=test_search_image,
        host=host,
        search_modality=query_fields,
    )
    search_url = f'{url}/search-app/search'
    assert_search(search_url, request_body)

    if kwargs.secured:
        # test add email
        request_body = get_default_request_body(secured=kwargs.secured, host=host)
        request_body['user_emails'] = ['florian.hoenicke@jina.ai']
        response = requests.post(
            f'{url}/admin/updateUserEmails',
            json=request_body,
        )
        assert response.status_code == 200

        # add api key
        del request_body['user_emails']
        request_body['api_keys'] = ['my_key']
        response = requests.post(
            f'{url}/admin/updateApiKeys',
            json=request_body,
        )
        if response.status_code != 200:
            print(response.text)
            print(response.json()['message'])
            raise Exception(f'Response status is {response.status_code}')
        # the same search should work now
        request_body = get_search_request_body(
            dataset=dataset,
            kwargs=kwargs,
            test_search_image=test_search_image,
            host=host,
            search_modality=query_fields,
        )
        assert_search(search_url, request_body)
        # search with invalid api key
        del request_body['jwt']
        request_body['api_key'] = 'no_key'
        with pytest.raises(Exception):
            assert_search(search_url, request_body)


def get_search_request_body(
    dataset,
    kwargs,
    test_search_image,
    host,
    search_modality,
):
    request_body = get_default_request_body(host=host, secured=kwargs.secured)
    request_body['limit'] = 9
    # Perform end-to-end check via bff
    if search_modality == 'text':
        if dataset == DemoDatasetNames.BEST_ARTWORKS:
            search_text = 'impressionism'
        elif dataset == DemoDatasetNames.NFT_MONKEY:
            search_text = 'laser eyes'
        else:
            search_text = 'test'
        request_body['query'] = [
            {'name': 'text', 'value': search_text, 'modality': 'text'}
        ]
    elif search_modality == 'image':
        request_body['query'] = [
            {'name': 'blob', 'value': test_search_image, 'modality': 'image'}
        ]
    return request_body


def assert_deployment_response(response):
    assert response['bff'] == 'http://localhost:8080/api/v1/search-app/docs'
    assert response['playground'].startswith('http://localhost/')
    assert response['host'].startswith('grpcs://')
    assert response['host'].endswith('.wolf.jina.ai')


@pytest.mark.parametrize('dataset', ['custom_s3_bucket'])
@pytest.mark.parametrize('query_fields', ['image'])
def test_backend_custom_data(
    start_bff,
    start_playground,
    dataset: str,
    query_fields: str,
    cleanup,
    with_hubble_login_patch,
):
    kwargs = {
        'now': 'start',
        'flow_name': 'nowapi',
        'dataset_type': DatasetTypes.S3_BUCKET,
        'dataset_path': os.environ.get('S3_CUSTOM_DATA_PATH'),
        'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        'aws_region_name': 'eu-west-1',
        'index_fields': ['.jpeg'],
        'filter_fields': [],
        'proceed': True,
        'secured': False,
    }
    kwargs = Namespace(**kwargs)
    response = cli(args=kwargs)

    # Dump the flow details from response host to a tmp file for post cleanup
    flow_details = {'host': response['host']}
    with open(f'{cleanup}/flow_details.json', 'w') as f:
        json.dump(flow_details, f)

    assert_deployment_response(response)

    assert_search_custom_s3(host=response['host'], create_temp_link=False)
    assert_search_custom_s3(host=response['host'], create_temp_link=True)


def assert_search_custom_s3(host, create_temp_link=False):
    request_body = {
        'query': [{'name': 'text', 'value': 'Hello', 'modality': 'text'}],
        'limit': 9,
        'host': host,
        'create_temp_link': create_temp_link,
    }

    response = requests.post(
        f'http://localhost:8080/api/v1/search-app/search',
        json=request_body,
    )

    assert (
        response.status_code == 200
    ), f"Received code {response.status_code} with text: {response.json()['message']}"

    response_json = response.json()
    assert len(response_json) == 2
    for doc in response_json:
        field = list(doc['fields'].values())[0]
        if create_temp_link:
            assert not field['uri'].startswith('s3://'), f"received: {doc}"
        else:
            assert field['uri'].startswith('s3://'), f"received: {doc}"
        assert (
            'blob' not in field.keys() or field['blob'] is None or field['blob'] == ''
        )
