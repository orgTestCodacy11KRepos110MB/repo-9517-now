from now.executor.indexer.elastic.elastic_indexer import (
    FieldEmbedding,
    NOWElasticIndexer,
)


def test_generate_es_mappings(setup_service_running):
    """
    This test should check, whether the static
    generate_es_mappings method works as expected.
    """
    document_mappings = [
        FieldEmbedding('clip', 8, ['title']),
    ]
    es_indexer = NOWElasticIndexer(document_mappings=document_mappings)
    expected_mapping = {
        'properties': {
            'id': {'type': 'keyword'},
            'bm25_text': {'type': 'text', 'analyzer': 'standard'},
            'title-clip': {
                'properties': {
                    'embedding': {
                        'type': 'dense_vector',
                        'dims': '8',
                        'similarity': 'cosine',
                        'index': 'true',
                    }
                }
            },
        }
    }
    result = es_indexer.generate_es_mapping()
    assert result == expected_mapping


def test_index_and_search_with_multimodal_docs(
    setup_service_running, es_inputs, random_index_name
):
    """
    This test runs indexing with the NOWElasticIndexer using multimodal docs.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs

    indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        # es_config={'api_key': os.environ['ELASTIC_API_KEY']},
        # hosts='https://5280f8303ccc410295d02bbb1f3726f7.eu-central-1.aws.cloud.es.io:443',
        hosts='http://localhost:9200',
        index_name=random_index_name,
    )

    indexer.index(index_docs_map)
    # check if documents are indexed
    es = indexer.es
    res = es.search(index=random_index_name, size=100, query={'match_all': {}})
    assert len(res['hits']['hits']) == len(index_docs_map['clip'])
    results = indexer.search(
        query_docs_map,
        parameters={
            'get_score_breakdown': True,
            'apply_default_bm25': True,
            'default_semantic_scores': default_semantic_scores,
        },
    )
    # asserts about matches
    for (
        query_field,
        document_field,
        encoder,
        linear_weight,
    ) in default_semantic_scores:
        if encoder == 'bm25':
            assert 'bm25_normalized' in results[0].matches[0].scores
            assert 'bm25_raw' in results[0].matches[0].scores
            assert isinstance(
                results[0].matches[0].scores['bm25_normalized'].value, float
            )
            assert isinstance(results[0].matches[0].scores['bm25_raw'].value, float)
        else:
            score_string = '-'.join(
                [
                    query_field,
                    document_field,
                    encoder,
                    str(linear_weight),
                ]
            )
            assert score_string in results[0].matches[0].scores
            assert isinstance(results[0].matches[0].scores[score_string].value, float)


def test_list_endpoint(setup_service_running, es_inputs, random_index_name):
    """
    This test tests the list endpoint of the NOWElasticIndexer.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs
    es_indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        hosts='http://localhost:9200',
        index_name=random_index_name,
    )
    es_indexer.index(index_docs_map)
    result = es_indexer.list()
    assert len(result) == len(index_docs_map['clip'])
    limit = 1
    result_with_limit = es_indexer.list(parameters={'limit': limit})
    assert len(result_with_limit) == limit
    offset = 1
    result_with_offset = es_indexer.list(parameters={'offset': offset})
    assert len(result_with_offset) == len(index_docs_map['clip']) - offset


def test_delete_by_id(setup_service_running, es_inputs, random_index_name):
    """
    This test tests the delete endpoint of the NOWElasticIndexer, by deleting a list of IDs.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs
    es_indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        hosts='http://localhost:9200',
        index_name=random_index_name,
    )
    es_indexer.index(index_docs_map)
    # delete by id
    ids = [doc.id for doc in index_docs_map['clip']]
    es_indexer.delete(parameters={'ids': ids})

    es = es_indexer.es
    res = es.search(index=random_index_name, size=100, query={'match_all': {}})
    assert len(res['hits']['hits']) == 0


def test_delete_by_filter(setup_service_running, es_inputs, random_index_name):
    """
    This test tests the delete endpoint of the NOWElasticIndexer, by deleting a filter.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs
    index_name = random_index_name
    es_indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        hosts='http://localhost:9200',
        index_name=index_name,
    )
    es_indexer.index(index_docs_map)

    # delete by filter
    es_indexer.delete(parameters={'filter': {'tags__price': {'$gte': 0}}})

    es = es_indexer.es
    res = es.search(index=index_name, size=100, query={'match_all': {}})
    assert len(res['hits']['hits']) == 0


def test_custom_mapping_and_custom_bm25_search(
    setup_service_running, es_inputs, random_index_name
):
    """
    This test tests the custom mapping and bm25 functionality of the NOWElasticIndexer.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs
    es_mapping = {
        'properties': {
            'id': {'type': 'keyword'},
            'bm25_text': {'type': 'text', 'analyzer': 'standard'},
            'title-clip': {
                'properties': {
                    'embedding': {
                        'type': 'dense_vector',
                        'dims': '8',
                        'similarity': 'cosine',
                        'index': 'true',
                    }
                }
            },
            'gif-clip': {
                'properties': {
                    'embedding': {
                        'type': 'dense_vector',
                        'dims': '8',
                        'similarity': 'cosine',
                        'index': 'true',
                    }
                }
            },
        }
    }
    es_indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        es_mapping=es_mapping,
        hosts='http://localhost:9200',
        index_name=random_index_name,
    )
    # do indexing
    es_indexer.index(index_docs_map)
    # search with custom bm25 query with field boosting
    custom_bm25_query = {
        'multi_match': {
            'query': 'this cat is cute',
            'fields': ['bm25_text^7'],
            'tie_breaker': 0.3,
        }
    }
    results = es_indexer.search(
        query_docs_map,
        parameters={
            'get_score_breakdown': True,
            'custom_bm25_query': custom_bm25_query,
            'default_semantic_scores': default_semantic_scores,
        },
    )
    assert len(results[0].matches) == 2
    assert results[0].matches[0].id == '0'
    assert results[0].matches[1].id == '1'


def test_search_with_filter(setup_service_running, es_inputs, random_index_name):
    """
    This test tests the search endpoint of the NOWElasticIndexer using filters.
    """
    (
        index_docs_map,
        query_docs_map,
        document_mappings,
        default_semantic_scores,
    ) = es_inputs
    index_name = random_index_name
    es_indexer = NOWElasticIndexer(
        document_mappings=document_mappings,
        hosts='http://localhost:9200',
        index_name=index_name,
    )
    es_indexer.index(index_docs_map)

    res = es_indexer.search(
        query_docs_map,
        parameters={
            'get_score_breakdown': True,
            'apply_default_bm25': True,
            'default_semantic_scores': default_semantic_scores,
            'filter': {'tags__price': {'$lte': 1}},
        },
    )
    assert len(res[0].matches) == 1
    assert res[0].matches[0].tags['price'] < 1
