import os

import pytest
from docarray import Document, DocumentArray
from jina import Flow

from now.executor.gateway import NOWGateway
from now.executor.preprocessor import NOWPreprocessor


@pytest.mark.parametrize('endpoint', ['index', 'search'])
def test_search_app(resources_folder_path, endpoint, tmpdir, mm_dataclass):

    metas = {'workspace': str(tmpdir)}
    text_docs = DocumentArray(
        [
            Document(mm_dataclass(text='test')),
            Document(
                mm_dataclass(
                    video=os.path.join(resources_folder_path, 'gif/folder1/file.gif')
                )
            ),
        ]
    )

    with Flow().config_gateway(
        uses=NOWGateway,
        protocol=['http'],
        port=8081,
        env={'JINA_LOG_LEVEL': 'DEBUG'},
        uses_with={'with_playground': False},
    ).add(uses=NOWPreprocessor, uses_metas=metas) as f:
        result = f.post(
            on=f'/{endpoint}',
            inputs=text_docs,
            show_progress=True,
        )
        result = DocumentArray.from_json(result.to_json())

    assert len(result) == 2
    assert result[0].text == ''
    assert result[0].chunks[0].chunks[0].text == 'test'
    assert result[1].chunks[0].chunks[0].blob
