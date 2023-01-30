from typing import Callable

import pytest
import requests
from docarray import Document, DocumentArray
from starlette import status


def test_text_search_fails_with_incorrect_query(client):
    with pytest.raises(ValueError):
        client.post(
            f'/api/v1/search-app/search',
            json={
                'data': [
                    (
                        [{'name': 'text', 'value': 'Hello', 'modality': 'text'}],
                        [
                            {
                                'name': 'uri',
                                'value': 'example.png',
                                'modality': 'image',
                            }
                        ],
                        [],
                    )
                ]
            },
        )


def test_text_search_fails_with_empty_query(client: requests.Session):
    with pytest.raises(ValueError):
        client.post(
            f'/api/v1/search-app/search',
            json={},
        )


def test_image_search_calls_flow(
    client_with_mocked_jina_client: Callable[[DocumentArray], requests.Session],
    sample_search_response_text: DocumentArray,
    base64_image_string: str,
):
    response = client_with_mocked_jina_client(sample_search_response_text).post(
        '/api/v1/search-app/search',
        json={
            'query': [
                {'name': 'blob', 'value': base64_image_string, 'modality': 'image'},
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    results = DocumentArray.from_json(response.content)
    # the mock writes the call args into the response tags
    assert results[0].tags['url'] == '/search'
    assert results[0].tags['parameters']['limit'] == 10


def test_multimodal_search_calls_flow(
    client_with_mocked_jina_client: Callable[[DocumentArray], requests.Session],
    sample_search_response_text: DocumentArray,
    base64_image_string: str,
):
    response = client_with_mocked_jina_client(sample_search_response_text).post(
        '/api/v1/search-app/search',
        json={
            'query': [
                {'name': 'blob', 'value': base64_image_string, 'modality': 'image'},
                {'name': 'text', 'value': 'Hello', 'modality': 'text'},
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    results = DocumentArray.from_json(response.content)
    # the mock writes the call args into the response tags
    assert results[0].tags['parameters']['limit'] == 10


def test_image_search_parse_response(
    client_with_mocked_jina_client: Callable[[DocumentArray], requests.Session],
    sample_search_response_text: DocumentArray,
    base64_image_string: str,
):
    response_raw = client_with_mocked_jina_client(sample_search_response_text).post(
        '/api/v1/search-app/search',
        json={
            'query': [
                {'name': 'blob', 'value': base64_image_string, 'modality': 'image'},
            ]
        },
    )

    assert response_raw.status_code == status.HTTP_200_OK
    results = DocumentArray()
    # todo: use multimodal doc in the future
    for response_json in response_raw.json():
        content = list(response_json['fields'].values())[0]
        doc = Document(
            id=response_json['id'],
            tags=response_json['tags'],
            scores=response_json['scores'],
            **content,
        )
        results.append(doc)
    assert len(results) == len(sample_search_response_text[0].matches)
    assert results[0].text == sample_search_response_text[0].matches[0].text


def test_text_search_with_semantic_scores(
    client_with_mocked_jina_client: Callable[[DocumentArray], requests.Session],
    sample_search_response_text: DocumentArray,
    base64_image_string: str,
):
    """
    Test that semantic_scores can be passed as parameters to the search endpoint.
    """
    response = client_with_mocked_jina_client(sample_search_response_text).post(
        '/api/v1/search-app/search',
        json={
            'query': [
                {'name': 'text', 'value': 'this crazy text', 'modality': 'text'},
            ],
            'semantic_scores': [['text', 'text', 'clip', 1]],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    results = DocumentArray.from_json(response.content)
    # the mock writes the call args into the response tags
    assert results[0].tags['parameters']['semantic_scores']
