from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from now.executor.gateway.bff.app.v1.models.shared import (
    BaseRequestModel,
    ModalityModel,
)

_ProtoValueType = Optional[Union[bool, float, str, list, dict]]
_StructValueType = Union[
    _ProtoValueType, List[_ProtoValueType], Dict[str, _ProtoValueType]
]


class _NamedScore(BaseModel):
    value: Optional[float] = None


class IndexRequestModel(BaseRequestModel):
    data: List[Tuple[Dict[str, ModalityModel], Dict[str, Any]]] = Field(
        default=[({}, {})],
        description='List of tuples where each tuple contains a dictionary of data and a dictionary of tags. '
        'The data dictionary maps the field name to its value. ',
    )


class SearchRequestModel(BaseRequestModel):
    limit: int = Field(default=10, description='Number of matching results to return')
    filters: Optional[Dict[str, str]] = Field(
        default={},
        description='dictionary with filters for search results  {"tag_name" : "tag_value"}',
    )
    query: Dict[str, ModalityModel] = Field(
        default={},
        description='Nested dictionary where key can be only one of the following: ``query_text``, ``query_image``, '
        'or ``query_video`` for a query with text, image, or video respectively, and the value is a '
        'dictionary with either uri, blob, or text as key. '
        'E.g., ``{"query_image": {"uri": "https://example.com/image.jpg"}``',
    )
    create_temp_link: bool = Field(
        default=False,
        description='If true, a temporary link to the file is created. '
        'This is useful if the file is stored in a cloud bucket.',
    )


class SearchResponseModel(BaseModel):
    id: str = Field(
        default=..., nullable=False, description='Id of the matching result.'
    )
    scores: Optional[Dict[str, '_NamedScore']] = Field(
        description='Similarity score with respect to the query.'
    )
    tags: Optional[Dict[str, '_StructValueType']] = Field(
        description='Additional tags associated with the file.'
    )
    fields: Dict[str, ModalityModel] = Field(
        default={}, description='Dictionary which maps the field name to its value. '
    )

    class Config:
        case_sensitive = False
        arbitrary_types_allowed = True


class SuggestionRequestModel(BaseRequestModel):
    text: Optional[str] = Field(default=None, description='Text')


IndexRequestModel.update_forward_refs()
SearchRequestModel.update_forward_refs()
SearchResponseModel.update_forward_refs()
