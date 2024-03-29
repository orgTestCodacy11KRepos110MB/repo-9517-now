import os

import pytest
from docarray import Document, DocumentArray

from now.app.base.preprocess import preprocess_text
from now.app.image_text_retrieval.app import ImageTextRetrieval
from now.app.text_to_text_and_image.app import TextToTextAndImage
from now.app.text_to_video.app import TextToVideo
from now.constants import DatasetTypes
from now.data_loading.data_loading import load_data
from now.data_loading.transform_docarray import transform_docarray
from now.demo_data import DemoDatasetNames
from now.now_dataclasses import UserInput


def test_text_to_video_preprocessing_query():
    """Test if the text to video preprocessing works for queries"""
    app = TextToVideo()
    da = DocumentArray([Document(text='test')])
    da = transform_docarray(da, search_fields=[])
    da = app.preprocess(da)

    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].chunks[0].text == 'test'


def test_text_to_video_preprocessing_indexing(resources_folder_path):
    """Test if the text to video preprocessing works for indexing"""
    app = TextToVideo()
    da = DocumentArray(
        [Document(uri=os.path.join(resources_folder_path, 'gif/folder1/file.gif'))]
    )
    da = transform_docarray(da, search_fields=[])
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks[0].chunks) == 3
    assert da[0].chunks[0].chunks[0].blob != b''


@pytest.mark.parametrize(
    'app_cls,is_indexing',
    [
        (ImageTextRetrieval, False),
        (ImageTextRetrieval, True),
    ],
)
def test_text_preprocessing(app_cls, is_indexing):
    """Test if the text to text preprocessing works for queries and indexing"""
    app = app_cls()
    da = DocumentArray([Document(text='test')])
    da = transform_docarray(da, search_fields=[])
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].modality == 'text'
    assert da[0].chunks[0].text == ''
    assert da[0].chunks[0].chunks[0].text == 'test'


@pytest.mark.parametrize(
    'app_cls,is_indexing',
    [
        (ImageTextRetrieval, False),
        (ImageTextRetrieval, True),
    ],
)
def test_image_preprocessing(app_cls, is_indexing, resources_folder_path):
    """Test if the image to image preprocessing works for queries and indexing"""
    app = app_cls()
    uri = os.path.join(resources_folder_path, 'image/5109112832.jpg')
    da = DocumentArray([Document(uri=uri)])
    da = transform_docarray(da, search_fields=[])
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].chunks[0].modality == 'image'
    assert da[0].chunks[0].chunks[0].uri == uri
    assert da[0].chunks[0].chunks[0].content


@pytest.mark.skip(
    reason="Temporarily deactivated until music2music app is reactivated."
)
@pytest.mark.parametrize('is_indexing', [False, True])
def test_music_preprocessing(is_indexing, resources_folder_path):
    """Test if the music preprocessing works"""
    app = MusicToMusic()
    uri = os.path.join(
        resources_folder_path, 'music/0ac463f952880e622bc15962f4f75ea51a1861a1.mp3'
    )

    da = DocumentArray([Document(uri=uri)])
    da = transform_docarray(da, search_fields=[])
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks) == 0
    assert da[0].blob != b''


def test_preprocess_text():
    result = preprocess_text(Document(text='test. test', modality='text'))
    assert len(result.chunks) == 2


@pytest.mark.skip(reason="Temporarily deactivated.")
@pytest.mark.parametrize('is_indexing', [False, True])
def test_nested_preprocessing(is_indexing, get_task_config_path):
    user_input = UserInput()
    user_input.dataset_type = DatasetTypes.DEMO
    user_input.dataset_name = DemoDatasetNames.ES_ONLINE_SHOP_50
    app = TextToTextAndImage()

    if is_indexing:
        da = DocumentArray(load_data(app, user_input)[0])
        app._create_task_config(user_input=user_input, data_example=da[0])
    else:
        da = DocumentArray(Document(text='query text'))

    processed_da = app.preprocess(da)
    assert len(processed_da) == 1
    if is_indexing:
        assert len(processed_da[0].chunks) == 2
        assert processed_da[0].chunks[0].text
        assert processed_da[0].chunks[1].uri
    else:
        assert processed_da[0].text == 'query text'
