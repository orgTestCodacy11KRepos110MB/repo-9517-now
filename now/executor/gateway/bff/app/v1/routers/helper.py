import base64
import itertools
import os
from copy import deepcopy
from tempfile import TemporaryDirectory
from typing import Union

import filetype
from docarray import Document, DocumentArray
from fastapi import HTTPException, status
from jina import Client
from jina.excepts import BadServer, BadServerFlow

from now.constants import SUPPORTED_FILE_TYPES
from now.utils import get_flow_id

# streamer = GatewayStreamer.get_streamer()


def field_dict_to_mm_doc(
    field_dict: dict, data_class: type, field_names_to_dataclass_fields={}
) -> Document:
    """Converts a dictionary of field names to their values to a document.

    :param field_dict: key-value pairs of field names and their values
    :param data_class: @docarray.dataclass class which encapsulates the fields of the multimodal document
    :param field_names_to_dataclass_fields: mapping of field names to data class fields (e.g. {'title': 'text_0'})
    :return: multi-modal document
    """
    if len(field_dict) != 1:
        raise ValueError(
            f"Multi-modal document isn't supported yet. "
            f"Can only set one value but have {list(field_dict.keys())}"
        )

    with TemporaryDirectory() as tmp_dir:
        try:
            if field_names_to_dataclass_fields:
                field_dict_orig = deepcopy(field_dict)
                field_dict = {
                    field_name_data_class: field_dict_orig[file_name]
                    for file_name, field_name_data_class in field_names_to_dataclass_fields.items()
                }
            data_class_kwargs = {}
            for field_name_data_class, field_value in field_dict.items():
                # save blob into a temporary file such that it can be loaded by the multimodal class
                if field_value.blob:
                    base64_decoded = base64.b64decode(field_value.blob.encode('utf-8'))
                    file_ending = filetype.guess(base64_decoded)
                    if file_ending is None:
                        raise ValueError(
                            f'Could not guess file type of blob {field_value.blob}. '
                            f'Please provide a valid file type.'
                        )
                    file_ending = file_ending.extension
                    if file_ending not in itertools.chain(
                        *SUPPORTED_FILE_TYPES.values()
                    ):
                        raise ValueError(
                            f'File type {file_ending} is not supported. '
                            f'Please provide a valid file type.'
                        )
                    file_path = os.path.join(
                        tmp_dir, field_name_data_class + '.' + file_ending
                    )
                    with open(file_path, 'wb') as f:
                        f.write(base64_decoded)
                    field_value.blob = None
                    field_value.uri = file_path
                if field_value.content is not None:
                    data_class_kwargs[field_name_data_class] = field_value.content
                else:
                    raise ValueError(
                        f'Content of field {field_name_data_class} is None. '
                    )
            doc = Document(data_class(**data_class_kwargs))
        except BaseException as e:
            raise HTTPException(
                status_code=500,
                detail=f'Not a correctly encoded request. Please see the error stack for more information. \n{e}',
            )

    return doc


def get_jina_client(host: str, port: int) -> Client:
    if 'wolf.jina.ai' in host or 'dev.jina.ai' in host:
        return Client(host=host)
    else:
        return Client(host=host, port=port)


def jina_client_post(
    request_model,
    endpoint: str,
    docs: Union[Document, DocumentArray],
    parameters=None,
    *args,
    **kwargs,
) -> DocumentArray:
    """Posts to the endpoint of the Jina client.

    :param request_model: contains the request model of the flow
    :param endpoint: endpoint which shall be called, e.g. '/index' or '/search'
    :param docs: document(s) which shall be passed in
    :param parameters: parameters to pass to the executors, e.g. jwt for securitization or limit for search
    :param args: any additional arguments passed to the `client.post` method
    :param kwargs: any additional keyword arguments passed to the `client.post` method
    :return: response of `client.post`
    """
    if parameters is None:
        parameters = {}
    client = get_jina_client(host=request_model.host, port=request_model.port)
    auth_dict = {}
    if request_model.api_key is not None:
        auth_dict['api_key'] = request_model.api_key
    if request_model.jwt is not None:
        auth_dict['jwt'] = request_model.jwt
    try:
        # result = await streamer.stream_docs(
        #     exec_endpoint=endpoint,
        #     docs=docs,
        #     parameters={
        #         **auth_dict,
        #         **parameters,
        #         'access_paths': '@cc',
        #     },
        #     *args,
        #     **kwargs,
        # )

        result = client.post(
            endpoint,
            inputs=docs,
            parameters={
                **auth_dict,
                **parameters,
                'access_paths': '@cc',
            },
            *args,
            **kwargs,
        )
    except (BadServer, BadServerFlow) as e:
        flow_id = get_flow_id(request_model.host)
        raise handle_exception(e, flow_id)
    return result


def handle_exception(e, flow_id):
    if isinstance(e, BadServer):
        if 'not a valid user' in e.args[0].status.description.lower():
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='You are not authorised to use this flow',
            )
        else:
            return e
    elif isinstance(e, BadServerFlow):
        if 'no route matched' in e.args[0].lower():
            return Exception(f'Flow with ID {flow_id} can not be found')
        else:
            return e
