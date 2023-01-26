from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from deployment.bff.app.v1.models.shared import BaseRequestModel, ModalityModel

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
        example=[({'title': ModalityModel(text='this title')}, {'color': 'red'})],
    )


class SearchRequestModel(BaseRequestModel):
    limit: int = Field(
        default=10, description='Number of matching results to return', example=10
    )
    filters: Optional[Dict[str, str]] = Field(
        default={},
        description='dictionary with filters for search results',
        example={'tags__color': {'$eq': 'blue'}},
    )
    query: List[Dict] = Field(
        default={},
        description='List of dictionaries with query fields. Each dictionary represents a field in the query.',
        example=[
            {'name': 'title', 'modality': 'text', 'value': 'cute cats'},
            {
                'name': 'image',
                'modality': 'image',
                'value': 'https://example.com/image.jpg',
            },
        ],
    )
    create_temp_link: bool = Field(
        default=False,
        description='If true, a temporary link to the file is created. '
        'This is useful if the file is stored in a cloud bucket.',
        example=False,
    )
    semantic_scores: List[Tuple] = Field(
        default=None,
        description='List of tuples where each tuple contains a query_field, index_field, encoder_name and weight. '
        'This defines how scores should be calculated for documents.',
        example=[('query_text', 'title', 'encoderclip', 1.0)],
    )


class SearchResponseModel(BaseModel):
    id: str = Field(
        default=...,
        nullable=False,
        description='Id of the matching result.',
        example='123',
    )
    scores: Optional[Dict[str, '_NamedScore']] = Field(
        description='Similarity score with respect to the query.',
        example={'score': {'value': 0.5}},
    )
    tags: Optional[Dict[str, '_StructValueType']] = Field(
        description='Additional tags associated with the file.',
        example={'tags__price': {'$lt': 50.0}},
    )
    fields: Dict[str, ModalityModel] = Field(
        default={},
        description='Dictionary which maps the field name to its value.',
        example={
            'title': {'text': 'hello world'},
            'image': {'uri': 'https://example.com/image.jpg'},
        },
    )

    class Config:
        case_sensitive = False
        arbitrary_types_allowed = True


class SuggestionRequestModel(BaseRequestModel):
    text: Optional[str] = Field(default=None, description='Text', example='cute cats')


IndexRequestModel.update_forward_refs()
SearchRequestModel.update_forward_refs()
SearchResponseModel.update_forward_refs()
