import multiprocessing
import os
from time import sleep

import pytest
from docarray import Document, DocumentArray
from docarray.typing import Image, Text
from jina import Flow

from now.admin.utils import get_default_request_body
from now.constants import EXTERNAL_CLIP_HOST, DatasetTypes, Models
from now.data_loading.create_dataclass import create_dataclass
from now.data_loading.data_loading import load_data
from now.demo_data import DemoDatasetNames
from now.executor.gateway import NOWGateway
from now.executor.indexer.elastic import NOWElasticIndexer
from now.executor.preprocessor import NOWPreprocessor
from now.now_dataclasses import UserInput

BASE_URL = 'http://localhost:8081/api/v1'
SEARCH_URL = f'{BASE_URL}/search-app/search'


def get_request_body(secured):
    request_body = get_default_request_body(secured=secured)
    return request_body


@pytest.fixture
def get_flow(request, random_index_name, tmpdir):
    params = request.param
    if isinstance(params, tuple):
        preprocessor_args, indexer_args = params
    elif isinstance(params, str):
        docs, user_input = request.getfixturevalue(params)
        fields_for_mapping = (
            [
                user_input.field_names_to_dataclass_fields[field_name]
                for field_name in user_input.index_fields
            ]
            if user_input.field_names_to_dataclass_fields
            else user_input.index_fields
        )
        preprocessor_args = {}
        indexer_args = {
            'user_input_dict': {
                'filter_fields': user_input.filter_fields,
            },
            'document_mappings': [[Models.CLIP_MODEL, 512, fields_for_mapping]],
        }

    indexer_args['index_name'] = random_index_name
    event = multiprocessing.Event()
    flow = FlowThread(event, preprocessor_args, indexer_args, tmpdir)
    flow.start()
    while not flow.is_flow_ready():
        sleep(1)
    if isinstance(params, tuple):
        yield
    elif isinstance(params, str):
        yield docs, user_input
    event.set()
    sleep(1)
    flow.terminate()


class FlowThread(multiprocessing.Process):
    def __init__(self, event, preprocessor_args=None, indexer_args=None, tmpdir=None):
        multiprocessing.Process.__init__(self)

        self.event = event

        preprocessor_args = preprocessor_args or {}
        indexer_args = indexer_args or {}
        metas = {'workspace': str(tmpdir)}
        # set secured to True if preprocessor_args or indexer_args contain 'admin_emails'
        secured = 'admin_emails' in preprocessor_args or 'admin_emails' in indexer_args
        self.flow = (
            Flow()
            .config_gateway(
                uses=NOWGateway,
                protocol=['http'],
                port=[8081],
                uses_with={
                    'user_input_dict': {
                        'secured': secured,
                    },
                    'with_playground': False,
                },
                env={'JINA_LOG_LEVEL': 'DEBUG'},
            )
            .add(
                uses=NOWPreprocessor,
                uses_with=preprocessor_args,
                uses_metas=metas,
            )
            .add(
                host=EXTERNAL_CLIP_HOST,
                port=443,
                tls=True,
                external=True,
            )
            .add(
                uses=NOWElasticIndexer,
                uses_with={
                    'hosts': 'http://localhost:9200',
                    **indexer_args,
                },
                uses_metas=metas,
                no_reduce=True,
            )
        )

    def is_flow_ready(self):
        return self.flow.is_flow_ready()

    def run(self):
        with self.flow:
            while True:
                if self.event.is_set():
                    break


@pytest.fixture
def data_with_tags(mm_dataclass):
    docs = DocumentArray([Document(mm_dataclass(text_field='test')) for _ in range(10)])
    for index, doc in enumerate(docs):
        doc.tags['color'] = 'Blue Color' if index == 0 else 'Red Color'
        doc.tags['price'] = 0.5 + index

    return docs


@pytest.fixture
def simple_data(mm_dataclass):
    return DocumentArray([Document(mm_dataclass(text_field='test')) for _ in range(10)])


@pytest.fixture
def artworks_data():
    user_input = UserInput()
    user_input.admin_name = 'team-now'
    user_input.dataset_type = DatasetTypes.DEMO
    user_input.dataset_name = DemoDatasetNames.BEST_ARTWORKS
    user_input.index_fields = ['image']
    user_input.filter_fields = ['label']
    user_input.index_field_candidates_to_modalities = {'image': Image}
    docs = load_data(user_input)
    return docs, user_input


@pytest.fixture
def pop_lyrics_data():
    user_input = UserInput()
    user_input.admin_name = 'team-now'
    user_input.dataset_type = DatasetTypes.DEMO
    user_input.dataset_name = DemoDatasetNames.POP_LYRICS
    user_input.index_fields = ['lyrics']
    user_input.index_field_candidates_to_modalities = {'lyrics': Text}
    docs = load_data(user_input)
    return docs, user_input


@pytest.fixture
def elastic_data(setup_online_shop_db, es_connection_params):
    _, index_name = setup_online_shop_db
    connection_str, _ = es_connection_params
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.ELASTICSEARCH
    user_input.es_index_name = index_name
    user_input.index_fields = ['title']
    user_input.filter_fields = ['product_id']
    user_input.index_field_candidates_to_modalities = {'title': Text}
    user_input.filter_field_candidates_to_modalities = {'product_id': str}
    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )
    user_input.es_host_name = connection_str
    docs = load_data(user_input=user_input, data_class=data_class)
    return docs, user_input


@pytest.fixture
def local_folder_data(resources_folder_path):
    user_input = UserInput()
    user_input.admin_name = 'team-now'
    user_input.dataset_type = DatasetTypes.PATH
    user_input.dataset_path = os.path.join(resources_folder_path, 'subdirectories')
    user_input.index_fields = ['a.jpg', 'test.txt']
    user_input.filter_fields = ['color']
    user_input.index_field_candidates_to_modalities = {'a.jpg': Image, 'test.txt': Text}
    user_input.filter_field_candidates_to_modalities = {'color': str}
    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )
    docs = load_data(user_input, data_class=data_class)
    return docs, user_input
