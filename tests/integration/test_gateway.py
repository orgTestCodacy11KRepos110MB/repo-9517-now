import os

from docarray import Document, DocumentArray, dataclass
from docarray.typing import Text
from jina import Executor, Flow

from now.constants import NOW_GATEWAY_VERSION


def test_gateway_jinahub():
    os.environ['JINA_LOG_LEVEL'] = 'DEBUG'

    @dataclass
    class MMResult:
        title: Text
        desc: Text

    class DummyEncoder(Executor):
        @requests
        def foo(self, docs: DocumentArray, **kwargs):
            for index, doc in enumerate(docs):
                doc.matches = DocumentArray(
                    [
                        Document(
                            MMResult(
                                title=f'test title {index}: {i}',
                                desc=f'test desc {index}: {i}',
                            )
                        )
                        for i in range(10)
                    ]
                )
            return docs

    f = (
        Flow()
        .config_gateway(
            uses=f'jinahub+docker://2m00g87k/{NOW_GATEWAY_VERSION}',
            protocol=['grpc'],
        )
        .add(uses=DummyEncoder, name='encoder')
    )

    with f:
        # f.block()
        print('start')
        result = f.post(on='/search', inputs=Document(text='test'))
        result.summary()
        result[0].matches.summary()
        result[0].matches[0].summary()
