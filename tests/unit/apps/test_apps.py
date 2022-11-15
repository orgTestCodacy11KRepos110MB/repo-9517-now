from docarray import Document, DocumentArray

from now.app.text_to_text.app import TextToText
from now.common.options import construct_app
from now.constants import Apps, DatasetTypes
from now.now_dataclasses import UserInput


def test_app_attributes():
    """Test if all essential app attributes are defined"""
    for app in Apps():
        app_instance = construct_app(app)
        if app_instance.is_enabled:
            assert app_instance.app_name
            assert app_instance.description
            assert app_instance.input_modality
            assert app_instance.output_modality


def test_split_text_preprocessing():
    """Test if splitting of sentences is carried out when preprocessing text documents at indexing time"""
    app = TextToText()
    da = DocumentArray([Document(text='test. test')])
    new_da = app.preprocess(da=da, user_input=UserInput(), is_indexing=True)
    assert len(new_da) == 2


def test_split_text_preprocessing_not_index_demo():
    """Test if splitting of sentences is carried out when preprocessing text documents at indexing time"""
    app = TextToText()
    da = DocumentArray([Document(text='test. test')])
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.DEMO
    new_da = app.preprocess(da=da, user_input=user_input, is_indexing=False)
    assert len(new_da) == 1


def test_split_text_preprocessing_demo():
    """Test if splitting of sentences is carried out when preprocessing text documents at indexing time"""
    app = TextToText()
    da = DocumentArray([Document(text='test. test')])
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.DEMO
    new_da = app.preprocess(da=da, user_input=user_input, is_indexing=True)
    assert len(new_da) == 1
