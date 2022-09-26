import numpy as np
import pytest
from jina import Document, DocumentArray, Flow
from now_executors.NOWAnnLiteIndexer.executor import NOWAnnLiteIndexer

N = 10  # number of data points
Nu = 9  # number of data update
Nq = 10
D = 128  # dimentionality / number of features


def gen_docs(num, has_chunk=False):
    res = DocumentArray()
    k = np.random.random((num, D)).astype(np.float32)
    for i in range(num):
        doc = Document(
            id=f'{i}',
            text='parent',
            embedding=k[i],
            uri='my-parent-uri',
            tags={'parent_tag': 'value'},
        )
        if has_chunk:
            for j in range(2):
                doc.chunks.append(
                    Document(
                        id=f'{i}_{j}',
                        embedding=doc.embedding,
                        uri='my-parent-uri',
                        tags={'parent_tag': 'value'},
                    )
                )
            doc.embedding = None
        res.append(doc)
    return res


def docs_with_tags(N):
    prices = [10.0, 25.0, 50.0, 100.0]
    categories = ['comics', 'movies', 'audiobook']
    X = np.random.random((N, D)).astype(np.float32)
    docs = [
        Document(
            id=f'{i}',
            embedding=X[i],
            tags={
                'price': np.random.choice(prices),
                'category': np.random.choice(categories),
            },
        )
        for i in range(N)
    ]
    da = DocumentArray(docs)

    return da


def test_index(tmpdir):
    """Test indexing does not return anything"""
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        result = f.post(on='/index', inputs=docs, return_results=True)
        assert len(result) == 0


@pytest.mark.parametrize(
    'offset, limit', [(0, 0), (10, 0), (0, 10), (10, 10), (None, None)]
)
@pytest.mark.parametrize('has_chunk', [True, False])
def test_list(tmpdir, offset, limit, has_chunk):
    """Test list returns all indexed docs"""
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N, has_chunk=has_chunk)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        parameters = {}
        if offset is not None:
            parameters.update({'offset': offset, 'limit': limit})
        if has_chunk:
            parameters.update({'traversal_paths': '@c', 'chunks_size': 2})

        f.post(on='/index', inputs=docs, parameters=parameters)
        list_res = f.post(on='/list', parameters=parameters, return_results=True)
        print(limit)
        if offset is None:
            l = N
        else:
            l = max(limit - offset, 0)
        assert len(list_res) == l
        if l > 0:
            if has_chunk:
                assert len(list_res[0].chunks) == 0
                assert len(set([d.id for d in list_res])) == l
                assert [d.id for d in list_res] == [f'{i}_0' for i in range(l)]
                assert [d.uri for d in list_res] == ['my-parent-uri'] * l
                assert [d.tags['parent_tag'] for d in list_res] == ['value'] * l
            else:
                assert list_res[0].id == str(offset) if offset is not None else '0'
                assert list_res[0].uri == 'my-parent-uri'
                assert len(list_res[0].chunks) == 0
                assert list_res[0].embedding is None
                assert list_res[0].text == ''
                assert list_res[0].tags == {'parent_tag': 'value'}


def test_update(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    docs_update = gen_docs(Nu)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        update_res = f.post(on='/update', inputs=docs_update, return_results=True)
        assert len(update_res) == Nu

        status = f.post(on='/status', return_results=True)[0]

        assert int(status.tags['total_docs']) == N
        assert int(status.tags['index_size']) == N


def test_search(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    docs_query = gen_docs(Nq)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)

        query_res = f.post(on='/search', inputs=docs_query, return_results=True)
        assert len(query_res) == Nq

        for i in range(len(query_res[0].matches) - 1):
            assert (
                query_res[0].matches[i].scores['cosine'].value
                <= query_res[0].matches[i + 1].scores['cosine'].value
            )


def test_search_match(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N, has_chunk=True)
    docs_query = gen_docs(Nq, has_chunk=True)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
            'index_traversal_paths': '@c',
            'search_traversal_paths': '@c',
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)

        query_res = f.post(
            on='/search',
            inputs=docs_query,
            parameters={'limit': 15},
            return_results=True,
        )
        c = query_res[0]
        assert c.embedding is None
        assert c.matches[0].embedding is None
        assert len(c.matches) == N

        for i in range(len(c.matches) - 1):
            assert (
                c.matches[i].scores['cosine'].value
                <= c.matches[i + 1].scores['cosine'].value
            )


def test_search_with_filtering(tmpdir):
    metas = {'workspace': str(tmpdir)}

    docs = docs_with_tags(N)
    docs_query = gen_docs(1)
    columns = ['price', 'float', 'category', 'str']

    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={'dim': D, 'columns': columns},
        uses_metas=metas,
    )

    with f:
        f.post(on='/index', inputs=docs)
        query_res = f.post(
            on='/search',
            inputs=docs_query,
            return_results=True,
            parameters={'filter': {'price': {'$lt': 50.0}}, 'include_metadata': True},
        )
        assert all([m.tags['price'] < 50 for m in query_res[0].matches])


def test_delete(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        docs[0].tags['parent_tag'] = 'different_value'
        f.post(on='/index', inputs=docs)
        status = f.post(on='/status', return_results=True)[0]
        assert int(status.tags['total_docs']) == N
        assert int(status.tags['index_size']) == N

        f.post(
            on='/delete',
            parameters={'filter': {'tags__parent_tag': {'$eq': 'different_value'}}},
        )
        status = f.post(on='/status', return_results=True)[0]
        assert int(status.tags['total_docs']) == N - 1
        assert int(status.tags['index_size']) == N - 1

        doc_list = f.post(on='/list')
        assert len(doc_list) == N - 1

        docs_query = gen_docs(Nq)
        f.post(on='/search', inputs=docs_query, return_results=True)


def test_status(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        status = f.post(on='/status', return_results=True)[0]
        assert int(status.tags['total_docs']) == N
        assert int(status.tags['index_size']) == N


def test_get_tags(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = DocumentArray(
        [
            Document(
                text='hi',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'red'},
            ),
            Document(
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'blue'},
            ),
            Document(
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                uri='file_will.never_exist',
            ),
        ]
    )
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        response = f.post(on='/tags')
        assert response[0].text == 'tags'
        assert 'tags' in response[0].tags
        assert 'color' in response[0].tags['tags']
        assert response[0].tags['tags']['color'] == ['red', 'blue'] or response[0].tags[
            'tags'
        ]['color'] == ['blue', 'red']


def test_delete_tags(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = DocumentArray(
        [
            Document(
                text='hi',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'red'},
            ),
            Document(
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'blue'},
            ),
            Document(
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                uri='file_will.never_exist',
            ),
            Document(
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'greeting': 'hello'},
            ),
        ]
    )
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        f.post(
            on='/delete',
            parameters={'filter': {'tags__color': {'$eq': 'blue'}}},
        )
        response = f.post(on='/tags')
        assert response[0].text == 'tags'
        assert 'tags' in response[0].tags
        assert 'color' in response[0].tags['tags']
        assert response[0].tags['tags']['color'] == ['red']
        f.post(
            on='/delete',
            parameters={'filter': {'tags__greeting': {'$eq': 'hello'}}},
        )
        response = f.post(on='/tags')
        assert 'greeting' not in response[0].tags['tags']


def test_update_tags(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = DocumentArray(
        [
            Document(
                id='1',
                text='hi',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'red'},
            ),
            Document(
                id='2',
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'color': 'blue'},
            ),
            Document(
                id='3',
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                uri='file_will.never_exist',
            ),
            Document(
                id='4',
                blob=b'b12',
                embedding=np.random.rand(D).astype(np.float32),
                tags={'greeting': 'hello'},
            ),
        ]
    )
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        f.post(
            on='/update',
            inputs=DocumentArray(
                [
                    Document(
                        id='3',
                        blob=b'b12',
                        embedding=np.random.rand(D).astype(np.float32),
                        tags={'new_tag': 'new_value'},
                    ),
                    Document(
                        id='4',
                        blob=b'b12',
                        embedding=np.random.rand(D).astype(np.float32),
                    ),
                ]
            ),
        )
        response = f.post(on='/tags')
        assert response[0].text == 'tags'
        assert 'tags' in response[0].tags
        assert 'color' in response[0].tags['tags']
        assert 'new_tag' in response[0].tags['tags']
        assert 'greeting' not in response[0].tags['tags']
        assert response[0].tags['tags']['color'] == ['red', 'blue'] or response[0].tags[
            'tags'
        ]['color'] == ['blue', 'red']
        assert response[0].tags['tags']['new_tag'] == ['new_value']


def test_clear(tmpdir):
    metas = {'workspace': str(tmpdir)}
    docs = gen_docs(N)
    f = Flow().add(
        uses=NOWAnnLiteIndexer,
        uses_with={
            'dim': D,
        },
        uses_metas=metas,
    )
    with f:
        f.post(on='/index', inputs=docs)
        f.post(on='/clear', return_results=True)
        status = f.post(on='/status', return_results=True)[0]
        assert int(status.tags['total_docs']) == 0
        assert int(status.tags['index_size']) == 0
