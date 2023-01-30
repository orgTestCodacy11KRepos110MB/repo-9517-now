import json
import os
from argparse import Namespace

import pytest
from tests.integration.remote.assertions import (
    assert_deployment_response,
    assert_search_custom_s3,
)

from now.cli import cli
from now.constants import DatasetTypes, Models


@pytest.mark.remote
@pytest.mark.parametrize('dataset', ['custom_s3_bucket'])
@pytest.mark.parametrize('query_fields', ['image'])
def test_backend_custom_data(
    start_bff,
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
        '.jpeg_model': [Models.CLIP_MODEL],
        'filter_fields': [],
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
