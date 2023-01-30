from docarray import Document, DocumentArray
from jina import Flow

from now.executor.autocomplete.executor import NOWAutoCompleteExecutor2
from now.executor.gateway import NOWGateway


def test_autocomplete(tmpdir, mm_dataclass):
    with Flow().config_gateway(
        uses=NOWGateway,
        protocol=['http'],
    ).add(uses=NOWAutoCompleteExecutor2, workspace=tmpdir) as f:
        f.post(
            on='/search',
            inputs=DocumentArray(
                [
                    Document(mm_dataclass(text='background')),
                    Document(mm_dataclass(text='background')),
                    Document(mm_dataclass(text='bang')),
                    Document(mm_dataclass(text='loading')),
                    Document(mm_dataclass(text='loading')),
                    Document(mm_dataclass(text='laugh')),
                    Document(mm_dataclass(text='hello')),
                    Document(mm_dataclass(text='red long dress')),
                ]
            ),
        )
        response = f.post(on='/suggestion', inputs=DocumentArray([Document(text='b')]))
        assert response[0].tags['suggestions'] == ['background', 'bang']
        response = f.post(on='/suggestion', inputs=DocumentArray([Document(text='l')]))
        assert response[0].tags['suggestions'] == ['loading', 'long', 'laugh']
        response = f.post(
            on='/suggestion', inputs=DocumentArray([Document(text='bac')])
        )
        assert response[0].tags['suggestions'] == ['background']
        response = f.post(
            on='/suggestion', inputs=DocumentArray([Document(text='fuc')])
        )
        assert response[0].tags['suggestions'] == []
        response = f.post(
            on='/suggestion', inputs=DocumentArray([Document(text='red')])
        )
        assert response[0].tags['suggestions'] == ['red', 'red long dress']
        response = f.post(on='/suggestion', inputs=DocumentArray([Document(text='d')]))
        assert response[0].tags['suggestions'] == ['dress']
