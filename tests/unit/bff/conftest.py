from typing import Callable, Dict, Generator, Optional

import pytest
import requests
from docarray import DocumentArray
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from now.executor.gateway.gateway.bff.app.app import build_app

data_url = 'https://storage.googleapis.com/jina-fashion-data/data/one-line/datasets/jpeg/best-artworks.img10.bin'


class MockedJinaClient:
    """
    This class is used to override the JinaClient dependency in the bff.
    On each call, it returns a `DocumentArray` with the call args in the `Document` tags.
    """

    def __init__(self, response: DocumentArray):
        self.response = response

    async def stream_docs(
        self, docs: DocumentArray, parameters: Optional[Dict] = None, *args, **kwargs
    ) -> DocumentArray:
        for doc in self.response.flatten():
            doc.tags['parameters'] = parameters
        yield self.response


@pytest.fixture
def client() -> Generator[requests.Session, None, None]:
    with TestClient(build_app()) as client:
        yield client


@pytest.fixture(scope='function')
def client_with_mocked_jina_client(
    mocker: MockerFixture,
) -> Callable[[DocumentArray], requests.Session]:
    def _fixture(response: DocumentArray) -> requests.Session:
        def _get_jina_streamer():
            return MockedJinaClient(response)

        mocker.patch(
            'now.executor.gateway.bff.app.v1.routers.helper.GatewayStreamer.get_streamer',
            _get_jina_streamer,
        )

        return TestClient(build_app())

    return _fixture
