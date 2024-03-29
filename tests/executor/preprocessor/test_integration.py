import json
import os

import pytest
from docarray import Document, DocumentArray
from jina import Flow

from now.constants import TAG_OCR_DETECTOR_TEXT_IN_DOC, Apps
from now.executor.preprocessor import NOWPreprocessor
from now.now_dataclasses import UserInput


def test_executor_persistence(tmpdir, resources_folder_path):
    e = NOWPreprocessor(Apps.IMAGE_TEXT_RETRIEVAL, metas={'workspace': tmpdir})
    user_input = UserInput()
    text_docs = DocumentArray(
        [
            Document(text='test'),
            Document(
                uri=os.path.join(resources_folder_path, 'image', '6785325056.jpg')
            ),
        ]
    )

    e.preprocess(
        docs=text_docs,
        parameters={'user_input': user_input.__dict__, 'is_indexing': False},
    )
    with open(e.user_input_path, 'r') as fp:
        json.load(fp)


@pytest.mark.parametrize('endpoint', ['index', 'search'])
def test_text_to_video(resources_folder_path, endpoint, tmpdir):
    metas = {'workspace': str(tmpdir)}
    app = Apps.TEXT_TO_VIDEO
    user_input = UserInput()
    text_docs = DocumentArray(
        [
            Document(text='test'),
            Document(uri=os.path.join(resources_folder_path, 'gif/folder1/file.gif')),
        ]
    )

    with Flow().add(
        uses=NOWPreprocessor, uses_with={'app': app}, uses_metas=metas
    ) as f:
        result = f.post(
            on=f'/{endpoint}',
            inputs=text_docs,
            parameters={'user_input': user_input.__dict__},
            show_progress=True,
        )
        result = DocumentArray.from_json(result.to_json())

    assert len(result) == 2
    assert result[0].text == ''
    assert result[0].chunks[0].chunks[0].text == 'test'
    assert result[1].chunks[0].chunks[0].blob
    assert TAG_OCR_DETECTOR_TEXT_IN_DOC not in result[0].chunks[0].chunks[0].tags
    assert TAG_OCR_DETECTOR_TEXT_IN_DOC in result[1].chunks[0].chunks[0].tags


def test_user_input_preprocessing():
    user_input = {'indexer_scope': {'text': 'title', 'image': 'uris'}}
    with Flow().add(
        uses=NOWPreprocessor, uses_with={'app': Apps.TEXT_TO_TEXT_AND_IMAGE}
    ) as f:
        result = f.post(
            on='/index',
            inputs=DocumentArray([Document(text='test')]),
            parameters={'user_input': user_input},
            show_progress=True,
        )
        result = DocumentArray.from_json(result.to_json())
