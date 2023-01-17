import random

import numpy as np
import pytest
from docarray import dataclass
from docarray.typing import Text
from jina import Document, DocumentArray, Executor, Flow, requests

from now.constants import TAG_OCR_DETECTOR_TEXT_IN_DOC
from now.executor.indexer.elastic import NOWElasticIndexer
from now.executor.preprocessor import NOWPreprocessor

NUMBER_OF_DOCS = 10
DIM = 128
MAX_RETRIES = 20
ENCODER_NAME = 'encoder'
DOCUMENT_MAPPINGS = [[ENCODER_NAME, DIM, ['title']]]


class DummyEncoder(Executor):
    @requests
    def foo(self, docs: DocumentArray, **kwargs):
        embeddings = np.random.random((len(docs), DIM)).astype(np.float32)
        for index, doc in enumerate(docs):
            doc.chunks[0].chunks[0].embedding = embeddings[index]
        return docs


@pytest.fixture
def flow(random_index_name, metas):
    f = (
        Flow()
        .add(
            uses=NOWPreprocessor,
            uses_metas=metas,
        )
        .add(uses=DummyEncoder, name=ENCODER_NAME)
        .add(
            uses=NOWElasticIndexer,
            uses_with={
                'hosts': 'http://localhost:9200',
                'index_name': random_index_name,
                'document_mappings': DOCUMENT_MAPPINGS,
                'user_input_dict': {
                    'filter_fields': ['color', 'greeting'],
                },
            },
            uses_metas=metas,
            no_reduce=True,
        )
    )
    return f


class TestElasticIndexer:
    def get_docs(self, num):
        prices = [10.0, 25.0, 50.0, 100.0]
        colors = ['blue', 'red']
        greetings = ['hello']
        res = DocumentArray()

        @dataclass
        class MMDoc:
            title: Text

        for i in range(num):
            doc = Document(
                MMDoc(
                    title=f'parent_{i}',
                )
            )
            doc.id = str(i)
            doc.tags['parent_tag'] = 'value'
            doc.tags['price'] = random.choice(prices)
            doc.tags['color'] = random.choice(colors)
            doc.tags['greeting'] = random.choice(greetings)
            res.append(doc)
        return res

    def get_query(self):
        @dataclass
        class MMQuery:
            query_text: Text

        return Document(MMQuery(query_text='query_1'))

    @pytest.fixture
    def random_index_name(self):
        return f"test-index-{random.randint(0, 10000)}"

    @pytest.fixture(scope='function', autouse=True)
    def metas(self, tmpdir):
        return {'workspace': str(tmpdir)}

    def test_index(self, metas, setup_service_running, flow):
        """Test indexing does not return anything"""
        docs = self.get_docs(NUMBER_OF_DOCS)
        with flow:
            result = flow.post(on='/index', inputs=docs, return_results=True)
            assert len(result) == 0

    @pytest.mark.parametrize(
        'offset, limit', [(0, 10), (10, 0), (0, 0), (10, 10), (None, None)]
    )
    def test_list(self, metas, offset, limit, setup_service_running, flow):
        """Test list returns all indexed docs"""
        docs = self.get_docs(NUMBER_OF_DOCS)
        with flow:
            parameters = {}
            if offset is not None:
                parameters.update({'offset': offset, 'limit': limit})

            flow.post(on='/index', inputs=docs, parameters=parameters)
            list_res = flow.post(on='/list', parameters=parameters, return_results=True)
            if offset is None:
                l = NUMBER_OF_DOCS
            else:
                l = max(limit - offset, 0)
            assert len(list_res) == l
            if l > 0:
                assert len(list_res[0].chunks) == 1
                assert isinstance(list_res[0].title, Document)
                assert len(set([d.id for d in list_res])) == l
                assert [d.tags['parent_tag'] for d in list_res] == ['value'] * l

    def test_search(self, metas, setup_service_running, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        docs_query = self.get_query()
        with flow:
            flow.post(on='/index', inputs=docs)

            query_res = flow.post(on='/search', inputs=docs_query, return_results=True)
            assert len(query_res) == 1

            for i in range(len(query_res[0].matches) - 1):
                assert (
                    query_res[0].matches[i].scores['cosine'].value
                    >= query_res[0].matches[i + 1].scores['cosine'].value
                )

    def test_search_match(self, metas, setup_service_running, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        docs_query = self.get_query()
        with flow:
            flow.post(on='/index', inputs=docs)

            query_res = flow.post(
                on='/search',
                inputs=docs_query,
                parameters={'limit': 15},
                return_results=True,
            )
            c = query_res[0]
            assert c.embedding is None
            assert c.matches[0].embedding is None
            assert len(c.matches) == NUMBER_OF_DOCS

            for i in range(len(c.matches) - 1):
                assert (
                    c.matches[i].scores['cosine'].value
                    >= c.matches[i + 1].scores['cosine'].value
                )

    def test_search_with_filtering(self, metas, setup_service_running, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        docs_query = self.get_query()
        with flow:
            flow.index(inputs=docs)
            query_res = flow.search(
                inputs=docs_query,
                return_results=True,
                parameters={'filter': {'tags__price': {'$lt': 50.0}}},
            )
            assert all([m.tags['price'] < 50 for m in query_res[0].matches])

    def test_delete(self, metas, setup_service_running, random_index_name, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        with flow:
            docs[0].tags['parent_tag'] = 'different_value'
            flow.post(on='/index', inputs=docs)
            listed_docs = flow.post(on='/list', return_results=True)
            assert len(listed_docs) == NUMBER_OF_DOCS
            flow.post(
                on='/delete',
                parameters={'filter': {'tags__parent_tag': {'$eq': 'different_value'}}},
            )
            listed_docs = flow.post(on='/list', return_results=True)
            assert len(listed_docs) == NUMBER_OF_DOCS - 1
            docs_query = self.get_query()
            flow.post(on='/search', inputs=docs_query, return_results=True)

    def test_get_tags(self, metas, setup_service_running, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        with flow:
            flow.post(on='/index', inputs=docs)
            response = flow.post(on='/tags')
            assert response[0].text == 'tags'
            assert 'tags' in response[0].tags
            assert 'color' in response[0].tags['tags']
            assert sorted(response[0].tags['tags']['color']) == sorted(['red', 'blue'])

    def test_delete_tags(self, metas, setup_service_running, flow):
        docs = self.get_docs(NUMBER_OF_DOCS)
        with flow:
            flow.index(
                docs,
            )
            flow.post(
                on='/delete',
                parameters={'filter': {'tags__color': {'$eq': 'blue'}}},
            )
            response = flow.post(on='/tags')
            assert response[0].text == 'tags'
            assert 'tags' in response[0].tags
            assert 'color' in response[0].tags['tags']
            assert 'blue' not in response[0].tags['tags']['color']
            flow.post(
                on='/delete',
                parameters={'filter': {'tags__greeting': {'$eq': 'hello'}}},
            )
            response = flow.post(on='/tags')
            assert 'hello' not in response[0].tags['tags']['greeting']

    @pytest.fixture()
    def documents(self):
        uri = 'https://jina.ai/assets/images/text-to-image-output.png'
        return DocumentArray(
            [
                Document(
                    id="doc1",
                    blob=b"gif...",
                    embedding=np.array([0.3, 0.1, 0.1]),
                    tags={'title': 'blue'},
                    uri=uri,
                    chunks=[
                        Document(
                            id="chunk11",
                            blob=b"jpg...",
                            embedding=np.array([0.1, 0.1]),
                            tags={
                                'title': 'that is rEd for sure',
                                TAG_OCR_DETECTOR_TEXT_IN_DOC: "r t",
                            },
                            uri=uri,
                        ),
                        Document(
                            id="chunk12",
                            blob=b"jpg...",
                            embedding=np.array([0.2, 0.1]),
                            tags={
                                'title': 'really bluE',
                                TAG_OCR_DETECTOR_TEXT_IN_DOC: "r t",
                            },
                            uri=uri,
                        ),
                    ],
                ),
                Document(
                    id="doc2",
                    blob=b"jpg...",
                    tags={'title': 'red', 'length': 18},
                    uri=uri,
                    embedding=np.array([0.4, 0.1, 0.1]),
                    chunks=[
                        Document(
                            id="chunk21",
                            blob=b"jpg...",
                            embedding=np.array([0.3, 0.1]),
                            tags={
                                'title': 'my red shirt',
                                TAG_OCR_DETECTOR_TEXT_IN_DOC: "red shirt",
                            },
                            uri=uri,
                        ),
                        Document(
                            id="chunk22",
                            blob=b"jpg...",
                            embedding=np.array([0.4, 0.1]),
                            tags={
                                'title': 'red is nice',
                                TAG_OCR_DETECTOR_TEXT_IN_DOC: "red shirt",
                            },
                            uri=uri,
                        ),
                    ],
                ),
                Document(
                    id="doc3",
                    blob=b"jpg...",
                    embedding=np.array([0.5, 0.1, 0.1]),
                    tags={'length': 18},
                    uri=uri,
                    chunks=[
                        Document(
                            id="chunk31",
                            blob=b"jpg...",
                            embedding=np.array([0.5, 0.1]),
                            tags={
                                'title': 'blue red',
                                TAG_OCR_DETECTOR_TEXT_IN_DOC: "i iz ret",
                            },
                            uri=uri,
                        ),
                    ],
                ),
                Document(
                    id="doc4",
                    blob=b"jpg...",
                    embedding=np.array([0.6, 0.1, 0.1]),
                    tags={'title': 'blue'},
                    uri=uri,
                ),
            ]
        )

    @pytest.mark.skip('not implemented for NOWElasticIndexer')
    @pytest.mark.parametrize(
        'query,embedding,res_ids',
        [
            ('blue', [0.5, 0.1], ['chunk12', 'chunk31', 'chunk22']),
            ('red', [0.5, 0.1], ['chunk11', 'chunk31', 'chunk22']),
        ],
    )
    def test_search_chunk_using_sum_ranker(
        self, metas, documents, setup_service_running, query, embedding, res_ids
    ):
        documents = DocumentArray([Document(chunks=[doc]) for doc in documents])
        with Flow().add(
            uses=NOWElasticIndexer,
            uses_with={
                "dim": len(embedding),
                "ocr_is_needed": True,
            },
            uses_metas=metas,
        ) as f:
            f.index(
                documents,
            )
            result = f.search(
                Document(
                    chunks=Document(
                        chunks=Document(
                            id="chunk_search",
                            text=query,
                            embedding=np.array(embedding),
                        ),
                    ),
                ),
                return_results=True,
            )
            print('all match ids', [match.id for match in result[0].matches])
            for d, res_id in zip(result[0].matches, res_ids):
                assert d.id == res_id
                if d.uri:
                    assert d.blob == b'', f'got blob {d.blob} for {d.id}'

    def test_curate_endpoint(self, metas, setup_service_running, flow):
        """Test indexing does not return anything"""
        docs = self.get_docs(NUMBER_OF_DOCS)

        with flow:
            flow.index(
                docs,
            )
            flow.post(
                on='/curate',
                parameters={
                    'query_to_filter': {
                        'query_1': [
                            {'text': {'$eq': 'parent_1'}},
                            {'tags__color': {'$eq': 'red'}},
                        ],
                        'query_2': [
                            {'text': {'$eq': 'parent_2'}},
                        ],
                    }
                },
            )
            query_doc = self.get_query()
            result = flow.search(
                inputs=query_doc,
                return_results=True,
            )

            assert len(result) == 1
            assert result[0].matches[0].title.text == 'parent_1'
            assert (
                result[0].matches[1].title.text != 'parent_1'
            )  # no duplicated results
            assert result[0].matches[1].tags['color'] == 'red'

            # not crashing in case of curated list + non-curated query
            non_curated_query = self.get_query()
            non_curated_query.query_text.text = 'parent_x'
            flow.search(inputs=non_curated_query)

    def test_curate_endpoint_incorrect(
        self, metas, setup_service_running, random_index_name, flow
    ):
        with flow:
            with pytest.raises(Exception):
                flow.post(
                    on='/curate',
                    parameters={'queryfilter': {}},
                )
