import base64

import pytest
from docarray import Document, DocumentArray, dataclass
from docarray.typing import Image, Text
from tests.integration.offline_flow.flow import OfflineFlow

from now.executor.gateway.gateway.bff.app.v1.models.search import SearchRequestModel
from now.executor.gateway.gateway.bff.app.v1.routers.search import search
from now.now_dataclasses import UserInput


def test_docarray(monkeypatch, setup_service_running, multi_modal_data):
    """
    Test all executors and bff together without creating a flow.
    The Clip Encoder is mocked because it is an external executor.
    Also, the network call for the bff is monkey patched.
    """
    user_input = UserInput()
    user_input.index_fields = ['product_title', 'product_description', 'product_image']

    offline_flow = OfflineFlow(monkeypatch, user_input_dict=user_input.__dict__)

    index_result = offline_flow.post(
        '/index',
        inputs=multi_modal_data,
        parameters={'access_paths': '@cc'},
    )

    assert index_result == DocumentArray()
    search_result = search(
        SearchRequestModel(
            query={'query_text': {'text': 'girl on motorbike'}},
        )
    )
    assert search_result[0].fields['product_title'].text == 'fancy title'
    assert search_result[0].fields['product_image'].blob != b''
    assert search_result[0].fields['product_description'].text == 'this is a product'


@pytest.fixture
def multi_modal_data(base64_image_string):
    @dataclass
    class Product:
        product_title: Text
        product_image: Image
        product_description: Text

    tensor = (
        Document(blob=base64.b64decode(base64_image_string))
        .convert_blob_to_image_tensor()
        .tensor
    )
    product = Product(
        product_title='fancy title',
        product_image=tensor,
        product_description='this is a product',
    )
    da = DocumentArray(Document(product))
    return da
