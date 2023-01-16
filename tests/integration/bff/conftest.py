from docarray import Document, DocumentArray, dataclass
from docarray.typing import Text
from jina import Flow

from now.constants import ACCESS_PATHS, EXTERNAL_CLIP_HOST
from now.executor.gateway.gateway import NOWGateway
from now.executor.indexer.elastic import NOWElasticIndexer
from now.executor.preprocessor import NOWPreprocessor

BASE_URL = 'http://localhost:8080/api/v1'
SEARCH_URL = f'{BASE_URL}/search-app/search'
HOST = 'grpc://0.0.0.0'
PORT = 9089


def index_data(f, **kwargs):
    @dataclass
    class Doc:
        title: Text

    docs = DocumentArray([Document(Doc(title='test')) for _ in range(10)])
    for index, doc in enumerate(docs):
        doc.tags['color'] = 'blue' if index == 0 else 'red'

    f.index(
        docs,
        parameters={
            'access_paths': ACCESS_PATHS,
            **kwargs,
        },
    )


def get_flow(preprocessor_args=None, indexer_args=None, tmpdir=None):
    """
    :param preprocessor_args: additional arguments for the preprocessor,
        e.g. {'admin_emails': [admin_email]}
    :param indexer_args: additional arguments for the indexer,
        e.g. {'admin_emails': [admin_email]}
    """
    preprocessor_args = preprocessor_args or {}
    indexer_args = indexer_args or {}
    metas = {'workspace': str(tmpdir)}
    f = (
        Flow(port_expose=9089)
        .config_gateway(
            uses=NOWGateway,
            protocol=['http'],
        )
        .add(
            uses=NOWPreprocessor,
            uses_with=preprocessor_args,
            uses_metas=metas,
        )
        .add(
            host=EXTERNAL_CLIP_HOST,
            port=443,
            tls=True,
            external=True,
        )
        .add(
            uses=NOWElasticIndexer,
            uses_with={
                'hosts': 'http://localhost:9200',
                'document_mappings': [['encoderclip', 512, ['title']]],
                **indexer_args,
            },
            uses_metas=metas,
            no_reduce=True,
        )
    )
    return f
