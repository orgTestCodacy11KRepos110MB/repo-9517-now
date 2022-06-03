import base64
from typing import List

from docarray import Document, DocumentArray
from fastapi import APIRouter
from jina import Client

from deployment.bff.app.v1.models.music import (
    NowMusicIndexRequestModel,
    NowMusicResponseModel,
    NowMusicSearchRequestModel,
)
from deployment.bff.app.v1.routers.helper import process_query

router = APIRouter()


@router.post(
    "/index",
    summary='Add more data to the indexer',
)
def index(data: NowMusicIndexRequestModel):
    """
    Append the list of songs to the indexer. Each song data request should be
    `base64` encoded using human-readable characters - `utf-8`.
    """
    index_docs = DocumentArray()
    for audio in data.songs:
        base64_bytes = audio.encode('utf-8')
        message = base64.decodebytes(base64_bytes)
        index_docs.append(Document(blob=message))

    if 'wolf.jina.ai' in data.host:
        c = Client(host=data.host)
    else:
        c = Client(host=data.host, port=data.port)
    c.post('/index', index_docs)


@router.post(
    "/search",
    response_model=List[NowMusicResponseModel],
    summary='Search music data via text or music as query',
)
def search(data: NowMusicSearchRequestModel):
    """
    Retrieve matching songs for a given query. Song query should be `base64` encoded
    using human-readable characters - `utf-8`.
    """
    query_doc = process_query(data.text, blob=data.song)
    if 'wolf.jina.ai' in data.host:
        c = Client(host=data.host)
    else:
        c = Client(host=data.host, port=data.port)
    docs = c.post('/search', query_doc, parameters={"limit": data.limit})
    print(docs[0])
    print(docs[0].matches[0])
    return docs[0].matches.to_dict()
