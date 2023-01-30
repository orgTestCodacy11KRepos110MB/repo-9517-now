import requests
from docarray import dataclass
from docarray.typing import Text

from now.executor.gateway.bff.app.v1.models.search import SearchRequestModel
from now.executor.gateway.bff.app.v1.routers.helper import (
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

        @dataclass
        class DataClass:
            text_0: Text

        if 'text' in kwargs:
            query_doc = field_dict_to_mm_doc(
                {'text': kwargs.pop('text')},
                data_class=DataClass,
                modalities_dict={'text': Text},
                field_names_to_dataclass_fields={'text': 'text_0'},
            )
        else:
            raise Exception('query doc is empty')
        app_request = SearchRequestModel(
            host=f'grpcs://nowapi-{self.jcloud_id}.wolf.jina.ai',
            api_key=self.api_key,
            **kwargs,
        )
        response = jina_client_post(
            app_request,
            endpoint,
            inputs=query_doc,
            parameters={
                'limit': app_request.limit,
                'filter': app_request.filters,
                'semantic_scores': app_request.semantic_scores,
            },
        )
        return response
