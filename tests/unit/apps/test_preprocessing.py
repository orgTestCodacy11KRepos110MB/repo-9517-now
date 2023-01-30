import os

import pytest
from docarray import Document, DocumentArray

from now.app.base.preprocess import preprocess_text
from now.app.search_app import SearchApp


@pytest.fixture
def mm_text_data(mm_dataclass):
    """Fixture for text data"""

    return DocumentArray(
        [
            Document(mm_dataclass(text='test')),
        ]
    )


def test_search_app_preprocessing_query(mm_text_data):
    """Test if the text to video preprocessing works for queries"""
    app = SearchApp()
    da = app.preprocess(mm_text_data)

    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].chunks[0].text == 'test'


def test_search_app_preprocessing_indexing(resources_folder_path, mm_dataclass):
    """Test if the text to video preprocessing works for indexing"""

    app = SearchApp()
    da = DocumentArray(
        [
            Document(
                mm_dataclass(
                    video=os.path.join(resources_folder_path, 'gif/folder1/file.gif')
                ),
            )
        ]
    )
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks[0].chunks) == 3
    assert da[0].chunks[0].chunks[0].blob != b''


@pytest.mark.parametrize(
    'app_cls,is_indexing',
    [
        (SearchApp, False),
        (SearchApp, True),
    ],
)
def test_text_preprocessing(app_cls, is_indexing, mm_text_data):
    """Test if the text to text preprocessing works for queries and indexing"""
    app = app_cls()
    da = app.preprocess(mm_text_data)
    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].modality == 'text'
    assert da[0].chunks[0].text == ''
    assert da[0].chunks[0].chunks[0].text == 'test'


@pytest.mark.parametrize(
    'app_cls,is_indexing',
    [
        (SearchApp, False),
        (SearchApp, True),
    ],
)
def test_image_preprocessing(app_cls, is_indexing, resources_folder_path, mm_dataclass):
    """Test if the image to image preprocessing works for queries and indexing"""

    app = app_cls()
    uri = os.path.join(resources_folder_path, 'image/a.jpg')
    da = DocumentArray([Document(mm_dataclass(image=uri))])
    da = app.preprocess(da)
    assert len(da) == 1
    assert len(da[0].chunks) == 1
    assert da[0].chunks[0].chunks[0].modality == 'image'
    assert da[0].chunks[0].chunks[0].uri == uri
    assert da[0].chunks[0].chunks[0].content


def test_preprocess_text():
    result = preprocess_text(Document(text='test. test', modality='text'))
    assert len(result.chunks) == 2
