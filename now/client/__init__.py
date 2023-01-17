import json
import re

import requests
from jina.serve.runtimes.gateway.http.models import JinaResponseModel
from pydantic import BaseModel, parse_obj_as

from now.common.options import construct_app
from now.executor.gateway.gateway.bff.app.v1.models.search import (
    IndexRequestModel,
    SearchRequestModel,
    SearchResponseModel,
)
from now.executor.gateway.gateway.bff.app.v1.routers.helper import (
    field_dict_to_mm_doc,
    jina_client_post,
)


class Client:
    """
    This is the jina NOW client which can be used to run requests against apps which are deployed using jcloud.
    """

    def __init__(self, jcloud_id, app, api_key):
        self.jcloud_id = jcloud_id
        self.app = app
        self.api_key = api_key

    def send_request_bff(self, endpoint: str, **kwargs):
        request_body = {
            "host": f'grpcs://nowapi-{self.jcloud_id}.wolf.jina.ai',
            "api_key": self.api_key,
            **kwargs,
        }
        response = requests.post(
            f'https://nowrun.jina.ai/api/v1/{endpoint}',
            json=request_body,
        )
        return response

    def send_request(self, endpoint: str, **kwargs):
        """
        Client to run requests against a deployed flow
        """
        if endpoint != 'search':
            raise NotImplementedError('Only search endpoint is supported for now')

        if 'text' in kwargs:
            query_doc = field_dict_to_mm_doc(
                {'query_text': {'text': kwargs.pop('text')}}
            )

        app_request = SearchRequestModel(
            host=f'grpcs://nowapi-{self.jcloud_id}.wolf.jina.ai',
            api_key=self.api_key,
            **kwargs,
        )
        response = jina_client_post(
            app_request,
            endpoint,
            inputs=query_doc,
            parameters={'limit': app_request.limit, 'filter': app_request.filters},
        )
        return response
