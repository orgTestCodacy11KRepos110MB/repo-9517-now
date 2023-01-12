import base64
from typing import List

from docarray import Document, dataclass, field
from docarray.typing import Image, Text, Video
from fastapi import APIRouter

from now.executor.gateway.bff.app.v1.models.search import (
    SearchRequestModel,
    SearchResponseModel,
    SuggestionRequestModel,
)
from now.executor.gateway.bff.app.v1.routers.helper import (
    field_dict_to_mm_doc,
    jina_client_post,
)

router = APIRouter()


@router.post(
    "/search",
    response_model=List[SearchResponseModel],
    summary='Search data via query',
)
async def search(data: SearchRequestModel):
    # temporary class until actual mm docs are created.
    @dataclass
    class MMQueryDoc:
        query_text: Text = field(default=None)
        query_image: Image = field(default=None)
        query_video: Video = field(default=None)

    query_doc = field_dict_to_mm_doc(data.query, data_class=MMQueryDoc)

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
        },
        request_model=data,
    )
    matches = []
    for doc in docs[0].matches:
        doc.summary()
        # todo: use multimodal doc in the future
        scores = {}
        for score_name, named_score in doc.scores.items():
            scores[score_name] = named_score.to_dict()
        field_names = doc._metadata['multi_modal_schema'].keys()
        field_names_and_chunks = [
            [field_name, getattr(doc, field_name)] for field_name in field_names
        ]
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
                raise Exception('Result without content', doc.id, doc.tags)
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
