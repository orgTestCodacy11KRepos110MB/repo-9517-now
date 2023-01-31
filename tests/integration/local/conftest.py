import multiprocessing
from time import sleep

import pytest
from jina import Flow

from now.admin.utils import get_default_request_body
from now.constants import EXTERNAL_CLIP_HOST
from now.executor.gateway import NOWGateway
from now.executor.indexer.elastic import NOWElasticIndexer
from now.executor.preprocessor import NOWPreprocessor

BASE_URL = 'http://localhost:8081/api/v1'
SEARCH_URL = f'{BASE_URL}/search-app/search'
HOST = 'http://0.0.0.0'


def get_request_body(secured):
    request_body = get_default_request_body(secured=secured)
    return request_body


@pytest.fixture
def get_flow(request, random_index_name, tmpdir):
    preprocessor_args, indexer_args = request.param
    indexer_args['index_name'] = random_index_name
    event = multiprocessing.Event()
    flow = FlowThread(event, preprocessor_args, indexer_args, tmpdir)
    flow.start()
    while not flow.is_flow_ready():
        sleep(1)
    yield
    event.set()
    sleep(1)
    flow.terminate()


class FlowThread(multiprocessing.Process):
    def __init__(self, event, preprocessor_args=None, indexer_args=None, tmpdir=None):
        multiprocessing.Process.__init__(self)

        self.event = event

        preprocessor_args = preprocessor_args or {}
        indexer_args = indexer_args or {}
        metas = {'workspace': str(tmpdir)}
        # set secured to True if preprocessor_args or indexer_args contain 'admin_emails'
        secured = 'admin_emails' in preprocessor_args or 'admin_emails' in indexer_args
        self.flow = (
            Flow()
            .config_gateway(
                uses=NOWGateway,
                protocol=['http'],
                port=[8081],
                uses_with={
                    'user_input_dict': {
                        'secured': secured,
                    },
                    'with_playground': False,
                },
                env={'JINA_LOG_LEVEL': 'DEBUG'},
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
                    **indexer_args,
                },
                uses_metas=metas,
                no_reduce=True,
            )
        )

    def is_flow_ready(self):
        return self.flow.is_flow_ready()

    def run(self):
        with self.flow:
            while True:
                if self.event.is_set():
                    break
