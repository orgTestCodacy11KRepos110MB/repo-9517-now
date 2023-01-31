""" Module holds reusable fixtures """
import base64
import os
import random
from collections import namedtuple
from warnings import catch_warnings, filterwarnings

import hubble
import numpy as np
import pytest
from docarray import Document, DocumentArray, dataclass, field
from docarray.typing import Image, Text, Video
from elasticsearch import Elasticsearch
from tests.unit.data_loading.elastic.example_dataset import ExampleDataset
from tests.unit.data_loading.elastic.utils import delete_es_index
from urllib3.exceptions import InsecureRequestWarning, SecurityWarning

from now.data_loading.elasticsearch import ElasticsearchConnector
from now.deployment.deployment import cmd
from now.executor.indexer.elastic.elastic_indexer import wait_until_cluster_is_up
from now.executor.preprocessor import NOWPreprocessor


@pytest.fixture()
def mm_dataclass():
    """Fixture for mmdocs data"""

    @dataclass
    class MMDoc:
        text: Text = field(default=None)
        image: Image = field(default=None)
        video: Video = field(default=None)

    return MMDoc


@pytest.fixture()
def resources_folder_path(tests_folder_path) -> str:
    return os.path.join(tests_folder_path, 'resources')


@pytest.fixture()
def tests_folder_path() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture
def base64_image_string(resources_folder_path: str) -> str:
    with open(os.path.join(resources_folder_path, 'image', 'a.jpg'), 'rb') as f:
        binary = f.read()
        img_string = base64.b64encode(binary).decode('utf-8')
    return img_string


@pytest.fixture
def base64_image_string(resources_folder_path: str) -> str:
    with open(os.path.join(resources_folder_path, 'image', 'a.jpg'), 'rb') as f:
        binary = f.read()
        img_string = base64.b64encode(binary).decode('utf-8')
    return img_string


@pytest.fixture(scope='session')
def service_account_file_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '..', 'service_account.json'
    )


@pytest.fixture(autouse=True, scope='session')
def setup_env():
    os.environ['NOW_CI_RUN'] = 'True'
    # 1 and true are not working in the current core version therefore, we give it another value
    os.environ['JINA_OPTOUT_TELEMETRY'] = 'someValueToDeactivateTelemetry'
    os.environ['JCLOUD_LOGLEVEL'] = 'DEBUG'


@pytest.fixture()
def image_resource_path(resources_folder_path: str) -> str:
    return os.path.join(resources_folder_path, 'image')


@pytest.fixture()
def gif_resource_path(resources_folder_path: str) -> str:
    return os.path.join(resources_folder_path, 'gif')


@pytest.fixture
def admin_email():
    return 'alpha.omega@jina.ai'


@pytest.fixture
def user_email():
    return 'abc.def@jina.ai'


@pytest.fixture
def domain_user_email():
    return 'abc.def@test.ai'


@pytest.fixture
def mock_hubble_user_email(monkeypatch, user_email):
    class MockedClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_user_info(self, *args, **kwargs):
            return {
                'code': 200,
                'data': {'email': user_email},
            }

    monkeypatch.setattr(hubble, 'Client', MockedClient)


@pytest.fixture
def mock_hubble_domain_user_email(monkeypatch, domain_user_email):
    class MockedClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_user_info(self, *args, **kwargs):
            return {
                'code': 200,
                'data': {'email': domain_user_email},
            }

    monkeypatch.setattr(hubble, 'Client', MockedClient)


@pytest.fixture()
def mock_hubble_admin_email(monkeypatch, admin_email):
    class MockedClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_user_info(self, *args, **kwargs):
            return {
                'code': 200,
                'data': {'email': admin_email},
            }

    monkeypatch.setattr(hubble, 'Client', MockedClient)
    # hubble.Client = MockedClient


@pytest.fixture(scope="session")
def es_connection_params():
    connection_str = 'http://localhost:9200'
    connection_args = {'verify_certs': False}
    return connection_str, connection_args


@pytest.fixture(scope='session')
def setup_service_running(es_connection_params) -> None:
    docker_compose_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'resources/elastic/docker-compose.yml',
    )
    cmd(f'docker-compose -f {docker_compose_file} up -d')
    hosts, _ = es_connection_params
    wait_until_cluster_is_up(es=Elasticsearch(hosts=hosts), hosts=hosts)
    yield
    cmd('docker-compose -f tests/resources/elastic/docker-compose.yml down')


@pytest.fixture
def get_aws_info():
    dataset_path = os.environ.get('S3_SCHEMA_FOLDER_PATH')
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = 'eu-west-1'

    return dataset_path, aws_access_key_id, aws_secret_access_key, region


@pytest.fixture
def random_index_name():
    return f"test-index-{random.randint(0, 10000)}"


@pytest.fixture
def es_inputs(gif_resource_path) -> namedtuple:
    np.random.seed(42)

    @dataclass
    class MMDoc:
        title: Text
        excerpt: Text
        gif: Image

    @dataclass
    class MMQuery:
        query_text: Text

    document_mappings = [['clip', 8, ['title', 'gif']]]

    default_semantic_scores = [
        ('query_text', 'title', 'clip', 1),
        ('query_text', 'gif', 'clip', 1),
        ('query_text', 'my_bm25_query', 'bm25', 1),
    ]
    docs = [
        MMDoc(
            title='cat test title cat',
            excerpt='cat test excerpt cat',
            gif=os.path.join(gif_resource_path, 'folder1/file.gif'),
        ),
        MMDoc(
            title='test title dog',
            excerpt='test excerpt 2',
            gif=os.path.join(gif_resource_path, 'folder1/file.gif'),
        ),
    ]
    clip_docs = DocumentArray()
    # encode our documents
    for i, doc in enumerate(docs):
        prep_doc = Document(doc)
        prep_doc = NOWPreprocessor().preprocess(DocumentArray(prep_doc))[0]
        prep_doc.tags['color'] = random.choice(['red', 'blue', 'green'])
        prep_doc.tags['price'] = i + 0.5
        prep_doc.id = str(i)
        clip_doc = Document(prep_doc, copy=True)
        clip_doc.id = prep_doc.id

        clip_doc.title.chunks[0].embedding = np.random.random(8)
        clip_doc.gif.chunks[0].embedding = np.random.random(8)

        clip_docs.append(clip_doc)

    index_docs_map = {
        'clip': clip_docs,
    }

    query = MMQuery(query_text='cat')

    query_doc = Document(query)
    clip_doc = Document(query_doc, copy=True)
    clip_doc.id = query_doc.id

    preprocessor = NOWPreprocessor()
    da_clip = preprocessor.preprocess(DocumentArray([clip_doc]), {})

    clip_doc.query_text.chunks[0].embedding = np.random.random(8)

    query_docs_map = {
        'clip': da_clip,
    }
    EsInputs = namedtuple(
        'EsInputs',
        [
            'index_docs_map',
            'query_docs_map',
            'document_mappings',
            'default_semantic_scores',
        ],
    )
    return EsInputs(
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    )


@pytest.fixture
def setup_elastic_db(setup_service_running, es_connection_params):
    connection_str, connection_args = es_connection_params
    with catch_warnings():
        filterwarnings('ignore', category=InsecureRequestWarning)
        filterwarnings('ignore', category=SecurityWarning)
        with ElasticsearchConnector(
            connection_str=connection_str, connection_args=connection_args
        ) as es_connector:
            # return connector to interact with the es database
            yield es_connector

            index_list = list(es_connector.es.indices.get(index='*').keys())
            for index in index_list:
                es_connector.es.indices.delete(index=str(index))


@pytest.fixture
def online_shop_resources(resources_folder_path):
    corpus_path = os.path.join(
        resources_folder_path, 'text+image/online_shop_corpus.jsonl.gz'
    )
    mapping_path = os.path.join(
        resources_folder_path, 'text+image/online_shop_mapping.json'
    )
    return corpus_path, mapping_path, 'online_shop_data'


@pytest.fixture()
def setup_online_shop_db(setup_elastic_db, es_connection_params, online_shop_resources):
    """
    This fixture loads data from Online shop data into an Elasticsearch instance.
    """
    es_connector = setup_elastic_db
    connection_str, connection_args = es_connection_params
    corpus_path, mapping_path, index_name = online_shop_resources

    # number of documents to import
    dataset_size = 50

    # load online shop data from some resource file
    dataset = ExampleDataset(corpus_path)
    dataset.import_to_elastic_search(
        connection_str=connection_str,
        connection_args=connection_args,
        index_name=index_name,
        mapping_path=mapping_path,
        size=dataset_size,
    )

    # return connector to interact with the es database
    yield es_connector, index_name

    # delete index
    delete_es_index(connector=es_connector, name=index_name)
