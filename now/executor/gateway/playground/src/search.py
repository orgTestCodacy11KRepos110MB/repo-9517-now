import base64
import functools
from collections.abc import Collection, Hashable, Mapping

import requests
import streamlit as st
from docarray import Document, DocumentArray
from docarray.score import NamedScore
from frozendict import frozendict

from now.constants import CG_BFF_PORT

from .constants import Parameters


def deep_freeze(thing):
    if thing is None or isinstance(thing, str):
        return thing
    elif isinstance(thing, Mapping):
        return frozendict({k: deep_freeze(v) for k, v in thing.items()})
    elif isinstance(thing, Collection):
        return tuple(deep_freeze(i) for i in thing)
    elif not isinstance(thing, Hashable):
        raise TypeError(f"un-freezable type: '{type(thing)}'")
    else:
        return thing


def deep_freeze_args(func):
    """
    Transform mutable dictionary into immutable. Useful to be compatible with cache.
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*deep_freeze(args), **deep_freeze(kwargs))

    return wrapped


def unfreeze_param(data):
    new_data = {}
    for k, v in data.items():
        if isinstance(v, frozendict):
            d = unfreeze_param(v)
            new_data[k] = dict(d)
        else:
            new_data[k] = v
    return new_data


def get_query_params() -> Parameters:
    query_parameters = st.experimental_get_query_params()
    parameters = Parameters()
    for key, val in query_parameters.items():
        if val is not None:
            setattr(
                parameters,
                key,
                val[0],
            )
    return parameters


def search(
    attribute_name,
    attribute_value,
    jwt,
    top_k=None,
    filter_dict=None,
    endpoint='search',
    field_name=None,
):
    print(f'Searching by {attribute_name}')
    params = get_query_params()
    post_url = f"http://localhost:{CG_BFF_PORT}/api/v1/search-app/{endpoint}"

    updated_dict = {}
    if filter_dict is not None:
        updated_dict = {k: v for k, v in filter_dict.items() if v != 'All'}
    data = {
        'host': params.host,
        'limit': top_k if top_k else params.top_k,
        'filters': updated_dict,
    }
    if endpoint == 'suggestion':
        data[attribute_name] = attribute_value
    elif endpoint == 'search':
        data['query'] = {f'query_{field_name}': {attribute_name: attribute_value}}
        data['create_temp_link'] = True
    # in case the jwt is none, no jwt will be sent. This is the case when no authentication is used for that flow
    if jwt is not None:
        data['jwt'] = jwt
    if params.port:
        data['port'] = params.port

    return post_bff(post_url, data, endpoint)


def get_suggestion(text, jwt):
    return search('text', text, jwt, endpoint='suggestion')


@deep_freeze_args
@functools.lru_cache(maxsize=10, typed=False)
def post_bff(url_host, data, endpoint):
    st.session_state.search_count += 1
    data = unfreeze_param(data)

    response = requests.post(
        url_host, json=data, headers={"Content-Type": "application/json; charset=utf-8"}
    )

    try:
        if endpoint == 'suggestion':
            docs = DocumentArray.from_json(response.content)
        elif endpoint == 'search':
            docs = DocumentArray()
            # todo: use multimodal doc in the future

            for response_json in response.json():
                chunks = []
                for name, type_to_content in sorted(response_json['fields'].items()):
                    chunk = Document(**type_to_content)
                    if chunk.blob:
                        base64_bytes = chunk.blob.encode('utf-8')
                        chunk.blob = base64.decodebytes(base64_bytes)

                    chunks.append(chunk)
                doc = Document(
                    id=response_json['id'],
                    tags=response_json['tags'],
                    chunks=chunks,
                )
                for metric, value in response_json['scores'].items():
                    doc.scores[metric] = NamedScore(value=value['value'])
                docs.append(doc)
    except Exception:
        try:
            json_response = response.json()

            if response.status_code == 401:
                st.session_state.error_msg = json_response['detail']
            else:
                st.session_state.error_msg = json_response['message'].replace('"', "'")
        except Exception:
            st.session_state.error_msg = response.text
        return None

    st.session_state.error_msg = None

    return docs


def search_by_text(search_text, jwt, filter_selection) -> DocumentArray:
    return search(
        'text', search_text, jwt, filter_dict=filter_selection, field_name='text'
    )


def search_by_image(document: Document, jwt, filter_selection) -> DocumentArray:
    """
    Wrap file in Jina Document for searching, and do all necessary conversion to make similar to indexed Docs
    """
    query_doc = document
    if query_doc.blob == b'':
        if query_doc.tensor is not None:
            query_doc.convert_image_tensor_to_blob()
        elif (query_doc.uri is not None) and query_doc.uri != '':
            query_doc.load_uri_to_blob(timeout=10)

    return search(
        'blob',
        base64.b64encode(query_doc.blob).decode('utf-8'),
        jwt,
        filter_dict=filter_selection,
        field_name='image',
    )
