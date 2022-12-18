import base64

from docarray import Document, DocumentArray
from fastapi import HTTPException

from deployment.bff.app.client import jina_client_post
from deployment.bff.app.endpoint.index import IndexEndpoint
from deployment.bff.app.endpoint.search import SearchEndpoint
from deployment.bff.app.endpoint.suggestion import SuggestionEndpoint
from deployment.bff.app.model_factory import get_pydantic_model


def map_inputs(inputs, request_modality):
    modality_list = inputs.get(f'{request_modality}_list', None)
    if not modality_list:
        modality_list = [inputs]
    da = DocumentArray()
    for modality_dict in modality_list:
        da.append(
            map_inputs_for_modality(
                modality_dict.get('text', None),
                modality_dict.get('blob', None),
                modality_dict.get('uri', None),
            )
        )
    return da


def map_inputs_for_modality(
    text: str = '', blob: str = b'', uri: str = None
) -> Document:
    """
    Processes query image or text  into a document and prepares the filetring query
    for the results.
    Currently we support '$and' between different conditions means we return results
    that have all the conditions. Also we only support '$eq' opperand for tag
    which means a tag should be equal to an exact value.
    Same query is passed to indexers, in docarray
    executor we do preprocessing by adding tags__ to the query

    :param text: text of the query
    :param blob: the blob of the image
    :param uri: uri of the ressource provided
    :param conditions: dictionary with the conditions to apply as filter
        tag should be the key and desired value is assigned as value
        to the key
    """
    if sum([bool(text), bool(blob), bool(uri)]) != 1:
        raise ValueError(
            f'Expected exactly one value to match but got: text={text}, blob={blob[:100] if blob else b""}, uri={uri}'
        )
    try:
        if uri:
            query_doc = Document(uri=uri)
        elif text:
            query_doc = Document(text=text, mime_type='text')
        elif blob:
            base64_bytes = blob.encode('utf-8')
            message_bytes = base64.decodebytes(base64_bytes)
            query_doc = Document(blob=message_bytes, mime_type='image')
        else:
            raise ValueError('None of the attributes uri, text or blob is set.')
    except BaseException as e:
        raise HTTPException(
            status_code=500,
            detail=f'Not a correct encoded query. Please see the error stack for more information. \n{e}',
        )
    return query_doc


def map_outputs(response_docs, endpoint_name, output_modality):
    if endpoint_name == 'index':
        return {}
    elif endpoint_name == 'suggestion':
        return response_docs.to_dict()
    else:
        return response_docs[0].matches.to_dict()


def get_endpoint_description(endpoint_name, input_modality, output_modality):
    if endpoint_name == 'search':
        return (
            f'Endpoint to send {endpoint_name} requests. '
            f'You can provide data of modality {input_modality} '
            f'and retrieve a list of outputs from {output_modality} modality.'
            f'You can also provide a filter conditions to only retrieve '
            f'certain documents.'
        )

    elif endpoint_name == 'index':
        return (
            f'Endpoint to {endpoint_name} documents. '
            f'You can provide a list of documents of type {input_modality} including tags.'
            f'The tags can be used to filter the documents when you send a search request.'
        )
    elif endpoint_name == 'suggestion':
        return f'Get auto complete suggestion for query.'
    else:
        raise ValueError(f'Unknown endpoint name {endpoint_name}')


def create_endpoints(router, input_modality, output_modality):
    for endpoint in [SearchEndpoint(), IndexEndpoint(), SuggestionEndpoint()]:
        if not endpoint.is_active(input_modality, output_modality):
            continue
        endpoint_name = endpoint.name
        request_modalities = endpoint.request_modality(input_modality, output_modality)
        response_modalities = endpoint.response_modality(
            input_modality, output_modality
        )
        RequestModel = get_pydantic_model(endpoint, request_modalities, is_request=True)
        ResponseModel = get_pydantic_model(
            endpoint, response_modalities, is_request=False
        )

        def get_endpoint(endpoint_name, request_modality, response_modality):
            """It is not allowed to use the same function name twice in the same scope.
            Therefore, we need to wrap the function in another function to get a new one.
            """

            def endpoint_fn(data: RequestModel) -> ResponseModel:
                data = data.dict()
                parameters = endpoint.get_parameters(data)
                print('### inputs before mapping', data)
                inputs = map_inputs(data, request_modality)
                print('### inputs after mapping', inputs)
                response_docs = jina_client_post(
                    endpoint=f'/{endpoint_name}',
                    inputs=inputs,
                    data=data,
                    parameters=parameters,
                )
                response = endpoint.map_outputs(response_docs)

                map_outputs(response_docs, endpoint_name, response_modality)
                return response

            return endpoint_fn

        router.add_api_route(
            f'/{endpoint_name}',
            endpoint=get_endpoint(
                endpoint_name, request_modalities, response_modalities
            ),
            methods=['POST'],
            response_model=ResponseModel,
            summary=f'Endpoint to send {endpoint_name} requests',
            description=get_endpoint_description(
                endpoint_name, input_modality, output_modality
            ),
            response_model_exclude_unset=True,
            response_model_exclude_none=True,
        )