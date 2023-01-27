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
    query: List[Dict] = Field(
        default={},
        description='List of dictionaries with query fields {"name": "field_name", "modality": "modality", "value": '
        '"value"}. Each dictionary represents a field in the query. Each dictionary must have a name, '
        'modality and value. The name is the name of the field in the data. The modality is the modality '
        'of the field. The value is the value of the field in the query. '
        'Example: [{"name": "title", "modality": "text", "value": "hello world"},'
        '          {"name": "image", "modality": "image", "value": "https://example.com/image.jpg"}]',
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
