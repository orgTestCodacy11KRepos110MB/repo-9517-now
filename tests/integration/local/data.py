import pytest
from docarray import Document, DocumentArray, dataclass
from docarray.typing import Image, Text

from now.constants import DatasetTypes
from now.data_loading.create_dataclass import create_dataclass
from now.data_loading.data_loading import load_data
from now.demo_data import DemoDatasetNames
from now.now_dataclasses import UserInput


@dataclass
class SimpleDoc:
    title: Text


@pytest.fixture
def data_with_tags():
    docs = DocumentArray([Document(SimpleDoc(title='test')) for _ in range(10)])
    for index, doc in enumerate(docs):
        doc.tags['color'] = 'Blue Color' if index == 0 else 'Red Color'
        doc.tags['price'] = 0.5 + index

    return docs


@pytest.fixture
def simple_data():
    return DocumentArray([Document(SimpleDoc(title='test')) for _ in range(10)])


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
