import pytest
from docarray import Document, DocumentArray, dataclass
from docarray.typing import Text


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
