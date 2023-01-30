from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

from docarray import Document, DocumentArray

metrics_mapping = {
    'cosine': 'cosineSimilarity',
    'l2_norm': 'l2norm',
}


def generate_semantic_scores(
    docs_map: Dict[str, DocumentArray],
    encoder_to_fields: Dict[str, Union[List[str], str]],
) -> List[Tuple]:
    """
    Generate semantic scores from document mappings.

    :param docs_map: dictionary mapping encoder to DocumentArray.
    :param encoder_to_fields: dictionary mapping encoder to fields.
    :return: a list of semantic scores, each of which is a tuple of
        (query_field, document_field, encoder, linear_weight).
        Semantic scores would then be for example:
        [('query_text', 'title', 'clip', 1.0)]
    """
    semantic_scores = []
    for executor_name, da in docs_map.items():
        first_doc = da[0]
        field_names = first_doc._metadata['multi_modal_schema'].keys()
        try:
            document_fields = encoder_to_fields[executor_name]
        except KeyError as e:
            raise KeyError(
                f'Documents are not encoded with same encoder as query. executor_name: {executor_name}, encoder_to_fields: {encoder_to_fields}'
            ) from e
        for field_name in field_names:
            chunk = getattr(first_doc, field_name)
            if chunk.chunks.embeddings is None and chunk.embedding is None:
                continue
            for document_field in document_fields:
                semantic_scores.append(
                    (
                        field_name,
                        document_field,
                        executor_name,
                        1,
                    )
                )

    return semantic_scores


def build_es_queries(
    docs_map,
    apply_default_bm25: bool,
    get_score_breakdown: bool,
    semantic_scores: List[Tuple],
    custom_bm25_query: Optional[dict] = None,
    metric: Optional[str] = 'cosine',
    filter: dict = {},
    query_to_curated_ids: Dict[str, list] = {},
) -> Dict:
    """
    Build script-score query used in Elasticsearch. To do this, we extract
    embeddings from the query document and pass them in the script-score
    query together with the fields to search on in the Elasticsearch index.
    The query document will be returned with all of its embeddings as tags with
    their corresponding field+encoder as key.

    :param docs_map: dictionary mapping encoder to DocumentArray.
    :param apply_default_bm25: whether to combine bm25 with vector search. If False,
        will only perform vector search. If True, must supply a text
        field for bm25 searching.
    :param get_score_breakdown: whether to return the score breakdown for matches.
        For this function, this parameter determines whether to return the embeddings
        of a query document.
    :param semantic_scores: list of semantic scores used to calculate a score for a document.
    :param custom_bm25_query: custom query to use for BM25.
    :param metric: metric to use for vector search.
    :param filter: dictionary of filters to apply to the search.
    :param query_to_curated_ids: dictionary mapping query text to list of curated ids.
    :return: a dictionary containing query and filter.
    """
    queries = {}
    pinned_queries = {}
    docs = {}
    sources = {}
    script_params = defaultdict(dict)
    for executor_name, da in docs_map.items():
        for doc in da:
            if doc.id not in docs:
                docs[doc.id] = doc
                docs[doc.id].tags['embeddings'] = {}

            if doc.id not in queries:
                queries[doc.id] = get_default_query(
                    doc,
                    apply_default_bm25,
                    semantic_scores,
                    custom_bm25_query,
                    filter,
                )
                pinned_queries[doc.id] = get_pinned_query(
                    doc,
                    query_to_curated_ids,
                )

                if apply_default_bm25 or custom_bm25_query:
                    sources[doc.id] = '1.0 + _score / (_score + 10.0)'
                else:
                    sources[doc.id] = '1.0'

            for (
                query_field,
                document_field,
                encoder,
                linear_weight,
            ) in get_scores(executor_name, semantic_scores):
                field_doc = getattr(doc, query_field)
                if get_score_breakdown:
                    docs[doc.id].tags['embeddings'][
                        f'{query_field}-{encoder}'
                    ] = field_doc.embedding

                query_string = f'params.query_{query_field}_{executor_name}'
                document_string = f'{document_field}-{encoder}'

                sources[
                    doc.id
                ] += f" + {float(linear_weight)}*{metrics_mapping[metric]}({query_string}, '{document_string}.embedding')"

                script_params[doc.id][
                    f'query_{query_field}_{executor_name}'
                ] = field_doc.embedding

    es_queries = []

    for doc_id, query in queries.items():
        script_score = {
            'script_score': {
                'query': {
                    'bool': query['bool'],
                },
                'script': {
                    'source': sources[doc_id],
                    'params': script_params[doc_id],
                },
            },
        }
        if pinned_queries[doc_id]:
            query_json = {'pinned': pinned_queries[doc_id]['pinned']}
            query_json['pinned']['organic'] = script_score
        else:
            query_json = script_score
        es_queries.append((docs[doc_id], query_json))
    return es_queries


def get_default_query(
    doc: Document,
    apply_default_bm25: bool,
    semantic_scores: List[Tuple],
    custom_bm25_query: Dict = None,
    filter: Dict = {},
):
    query = {
        'bool': {
            'should': [
                {'match_all': {}},
            ],
        },
    }

    # build bm25 part
    if apply_default_bm25:
        bm25_semantic_score = next((x for x in semantic_scores if x[2] == 'bm25'))
        if not bm25_semantic_score:
            raise ValueError(
                'No bm25 semantic scores found. Please specify this in the semantic_scores parameter.'
            )
        text = getattr(doc, bm25_semantic_score[0]).text
        multi_match = {'multi_match': {'query': text, 'fields': ['bm25_text']}}
        query['bool']['should'].append(multi_match)
    elif custom_bm25_query:
        query['bool']['should'].append(custom_bm25_query)

    # add filter
    if filter:
        es_search_filter = process_filter(filter)
        query['bool']['filter'] = es_search_filter

    return query


def get_pinned_query(doc: Document, query_to_curated_ids: Dict[str, list] = {}) -> Dict:
    pinned_query = {}
    if getattr(doc, 'query_text', None):
        query_text = doc.query_text.text
        if query_text in query_to_curated_ids.keys():
            pinned_query = {'pinned': {'ids': query_to_curated_ids[query_text]}}
    return pinned_query


def process_filter(filter) -> dict:
    es_search_filter = {}
    for field, filters in filter.items():
        for operator, filter in filters.items():
            field = field.replace('__', '.')
            if isinstance(filter, str):
                es_search_filter['term'] = {field: filter}
            elif isinstance(filter, int) or isinstance(filter, float):
                operator = operator.replace('$', '')
                es_search_filter['range'] = {field: {operator: filter}}
    return es_search_filter


def get_scores(encoder, semantic_scores):
    for (
        query_field,
        document_field,
        _encoder,
        linear_weight,
    ) in semantic_scores:
        if encoder == _encoder:
            yield query_field, document_field, _encoder, linear_weight
