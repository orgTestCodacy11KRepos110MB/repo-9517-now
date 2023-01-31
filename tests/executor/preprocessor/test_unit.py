import os
import shutil

from docarray import Document, DocumentArray

from now.executor.preprocessor import NOWPreprocessor

curdir = os.path.dirname(os.path.abspath(__file__))


def download_mock(url, destfile):
    path = f'{curdir}/../../{url.replace("s3://", "")}'
    shutil.copyfile(path, destfile)


def test_text(mm_dataclass):
    da_search = DocumentArray(
        [
            Document(
                mm_dataclass(
                    text_field='This is the first Sentence. This is the second Sentence.'
                )
            )
        ]
    )
    preprocessor = NOWPreprocessor()
    res_search = preprocessor.preprocess(da_search)
    assert len(res_search) == 1
    assert len(res_search[0].chunks) == 1
    result_strings = res_search[0].chunks[0].chunks.texts
    expected_strings = ['This is the first Sentence.', 'This is the second Sentence.']
    assert sorted(result_strings) == sorted(expected_strings)
