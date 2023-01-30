from docarray import Document
from docarray.typing import Text

from now.constants import DatasetTypes
from now.data_loading.create_dataclass import create_dataclass
from now.data_loading.data_loading import load_data
from now.now_dataclasses import UserInput


def test_elasticsearch_data_loading(setup_online_shop_db, es_connection_params):
    _, index_name = setup_online_shop_db
    connection_str, _ = es_connection_params
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.ELASTICSEARCH
    user_input.es_index_name = index_name
    user_input.index_fields = ['title']
    user_input.filter_fields = ['text']
    user_input.index_field_candidates_to_modalities = {'title': Text}
    user_input.filter_field_candidates_to_modalities = {'text': str}
    data_class, user_input.field_names_to_dataclass_fields = create_dataclass(
        user_input=user_input
    )
    user_input.es_host_name = connection_str

    transformed_docs = load_data(user_input=user_input, data_class=data_class)

    assert len(transformed_docs) == 50
    assert isinstance(transformed_docs[0], Document)
    assert len(transformed_docs[0].chunks) == 1
