import json
from argparse import Namespace

import pytest
from tests.integration.remote.assertions import (
    assert_deployment_queries,
    assert_deployment_response,
    assert_suggest,
    get_search_request_body,
)

from now.cli import cli
from now.constants import DatasetTypes, Models
from now.demo_data import DemoDatasetNames


@pytest.mark.remote
@pytest.mark.parametrize(
    'query_fields, index_fields, filter_fields, model_selection, dataset',
    [
        (
            'image',
            ['image', 'label'],
            [],
            {
                'image_model': [Models.CLIP_MODEL],
                'label_model': [Models.CLIP_MODEL, Models.SBERT_MODEL],
            },
            DemoDatasetNames.BIRD_SPECIES,
        ),
        (
            'image',
            ['image'],
            ['label'],
            {
                'image_model': [Models.CLIP_MODEL],
            },
            DemoDatasetNames.BIRD_SPECIES,
        ),
        (
            'text',
            ['lyrics'],
            [],
            {'lyrics_model': [Models.CLIP_MODEL, Models.SBERT_MODEL]},
            DemoDatasetNames.POP_LYRICS,
        ),
        (
            'text',
            ['video', 'description'],
            [],
            {
                'video_model': [Models.CLIP_MODEL],
                'description_model': [Models.CLIP_MODEL],
            },
            DemoDatasetNames.TUMBLR_GIFS_10K,
        ),
        (
            'text',
            ['image'],
            ['label'],
            {
                'image_model': [Models.CLIP_MODEL],
            },
            DemoDatasetNames.BEST_ARTWORKS,
        ),
    ],
)
@pytest.mark.timeout(60 * 10)
def test_end_to_end(
    cleanup,
    query_fields,
    index_fields,
    filter_fields,
    model_selection,
    dataset,
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
    }
    kwargs.update(model_selection)
    kwargs = Namespace(**kwargs)
    response = cli(args=kwargs)
    # Dump the flow details from response host to a tmp file
    flow_details = {'host': response['host']}
    with open(f'{cleanup}/flow_details.json', 'w') as f:
        json.dump(flow_details, f)

    assert_deployment_response(response)
    assert_deployment_queries(
        kwargs=kwargs,
        response=response,
        search_modality='text',
        dataset=dataset,
    )
    if query_fields == 'text':
        host = response.get('host')
        request_body = get_search_request_body(
            kwargs=kwargs,
            host=host,
            search_modality='text',
            dataset=dataset,
        )
        suggest_url = f'{response["host"]}/api/v1/search-app/suggestion'
        assert_suggest(suggest_url, request_body)
