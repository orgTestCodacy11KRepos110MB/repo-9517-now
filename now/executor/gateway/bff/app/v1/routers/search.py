import base64
from typing import List

from docarray import Document
from fastapi import APIRouter

from now.data_loading.create_dataclass import create_dataclass
from now.executor.gateway.bff.app.v1.models.search import (
    SearchRequestModel,
    SearchResponseModel,
    SuggestionRequestModel,
)
from now.executor.gateway.bff.app.v1.routers.helper import (
    field_dict_to_mm_doc,
    jina_client_post,
)
from now.utils import modality_string_to_docarray_typing

router = APIRouter()


@router.post(
    "/search",
    response_model=List[SearchResponseModel],
    summary='Search data via query',
)
async def search(data: SearchRequestModel):
    fields_modalities_mapping = {}
    fields_values_mapping = {}

    if len(data.query) == 0:
        raise ValueError('Query cannot be empty')

    for field in data.query:
        fields_modalities_mapping[field['name']] = modality_string_to_docarray_typing(
            field['modality']
        )
        fields_values_mapping[field['name']] = field['value']
    data_class, field_names_to_dataclass_fields = create_dataclass(
        fields=list(fields_modalities_mapping.keys()),
        fields_modalities=fields_modalities_mapping,
    )
    query_doc = field_dict_to_mm_doc(
        fields_values_mapping,
        data_class=data_class,
        modalities_dict=fields_modalities_mapping,
        field_names_to_dataclass_fields=field_names_to_dataclass_fields,
    )
    query_filter = {}
    for key, value in data.filters.items():
        key = 'tags__' + key if not key.startswith('tags__') else key
        query_filter[key] = {'$eq': value}

    docs = await jina_client_post(
        endpoint='/search',
        docs=query_doc,
        parameters={
            'limit': data.limit,
            'filter': query_filter,
            'create_temp_link': data.create_temp_link,
            'semantic_scores': data.semantic_scores,
        },
        request_model=data,
    )
    matches = []
    for doc in docs[0].matches:
        # todo: use multimodal doc in the future!
        scores = {}
        for score_name, named_score in doc.scores.items():
            scores[score_name] = named_score.to_dict()
        # since multimodal doc is not supported, we take the first chunk
        if doc.chunks:
            # temporary fix for filtering out tags
            field_names = [
                field
                for field in doc._metadata['multi_modal_schema'].keys()
                if doc._metadata['multi_modal_schema'][field]['attribute_type']
                != 'primitive'
            ]
            field_names_and_chunks = [
                [field_name, getattr(doc, field_name)] for field_name in field_names
            ]
        else:
            # TODO remove else path. It is only used to support the inmemory indexer since that one is operating on chunks while elastic responds with root documents
            field_names_and_chunks = [['result_field', doc]]
        results = {}
        for field_name, chunk in field_names_and_chunks:
            if chunk.blob:
                result = {'blob': base64.b64encode(chunk.blob).decode('utf-8')}
            elif chunk.text:
                result = {'text': chunk.text}
            elif chunk.uri:
                # in case we have content and uri, the content is preferred
                result = {'uri': chunk.uri}
            else:
                # We should not raise exception else it breaks the playground if a single chunk has no content
                # irrespective of what other chunks hold. We should just log it and move on.
                print('Result without content', doc.id, doc.tags)
                result = {'text': ''}
            results[field_name] = result
        match = SearchResponseModel(
            id=doc.id,
            scores=scores,
            tags=doc.tags,
            fields=results,
        )
        matches.append(match)
    return matches


@router.post(
    "/suggestion",
    summary='Get auto complete suggestion for query',
)
async def suggestion(data: SuggestionRequestModel):
    suggest_doc = Document(text=data.text)
    docs = await jina_client_post(
        endpoint='/suggestion',
        docs=suggest_doc,
        request_model=data,
        target_executor=r'\Aautocomplete_executor\Z',
    )
    return docs.to_dict()