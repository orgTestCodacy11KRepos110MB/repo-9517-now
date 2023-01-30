from typing import Dict, List, Optional

from elasticsearch.helpers import bulk

from now.data_loading.elasticsearch import ElasticsearchConnector


def delete_es_index(connector: ElasticsearchConnector, name: str) -> None:
    """
    Deletes an index.
    :param connector: Instance of `ElasticsearchConnector`
    :param name: Name of the index in the Elasticsearch database
    """
    connector.es.indices.delete(index=name)


def es_insert(
    connector: ElasticsearchConnector, index_name: str, documents: List[Dict]
) -> int:
    """
    Inserts a given list of documents into the Elasticsearch index with the given
        name.
    :param connector: Instance of `ElasticsearchConnector`
    :param index_name: Name of the Elasticsearch index for inserting the documents
    :param documents: List of documents in the form of a dictionary
    :return: Number of successfully inserted documents
    """
    for doc in documents:
        doc['_op_type'] = 'index'
        doc['_index'] = index_name
    success, _ = bulk(connector.es, documents, refresh='wait_for')
    return success


def create_es_index(
    connector: ElasticsearchConnector, name: str, mapping: Optional[Dict] = None
) -> None:
    """
    Creates a new index.
    :param connector: Instance of `ElasticsearchConnector`
    :param name: Name of the index in the Elasticsearch database
    :param mapping: Elasticsearch
        `mapping <https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html>`_
        which describes the fields of an ES document and how they are stored
    """  # noqa: E501
    if connector.es.indices.exists(index=name):
        connector.es.indices.delete(index=name)
    connector.es.indices.create(index=name, mappings=mapping)
