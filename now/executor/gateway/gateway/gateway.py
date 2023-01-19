import os

import jina
import streamlit.web.bootstrap
from docarray import Document, DocumentArray, dataclass
from docarray.typing import Text
from jina import Executor, Gateway, requests
from jina.serve.runtimes.gateway import CompositeGateway
from jina.serve.runtimes.gateway.http.fastapi import FastAPIBaseGateway
from jina.serve.runtimes.gateway.http.models import JinaHealthModel
from streamlit.web.server import Server as StreamlitServer

from now.executor.gateway.gateway.bff.app.app import application

cur_dir = os.path.dirname(__file__)


class PlaygroundGateway(Gateway):
    def __init__(self, **kwargs):
        print(f"jina version: {jina.__version__}")
        super().__init__(**kwargs)
        self.streamlit_script = 'playground/playground.py'

    async def setup_server(self):
        streamlit.web.bootstrap._fix_sys_path(self.streamlit_script)
        streamlit.web.bootstrap._fix_matplotlib_crash()
        streamlit.web.bootstrap._fix_tornado_crash()
        streamlit.web.bootstrap._fix_sys_argv(self.streamlit_script, ())
        streamlit.web.bootstrap._fix_pydeck_mapbox_api_warning()
        # streamlit.web.bootstrap._install_pages_watcher(self.streamlit_script)
        self.streamlit_server = StreamlitServer(
            os.path.join(cur_dir, self.streamlit_script),
            f'"python -m streamlit" run --browser.serverPort 12983 {self.streamlit_script} --server.address=0.0.0.0',
        )

    async def run_server(self):
        await self.streamlit_server.start()
        streamlit.web.bootstrap._on_server_start(self.streamlit_server)
        streamlit.web.bootstrap._set_up_signal_handler(self.streamlit_server)

    async def shutdown(self):
        self.streamlit_server.stop()


class BFFGateway(FastAPIBaseGateway):
    @property
    def app(self):
        # fix to use starlette instead of FastAPI app (throws warning that "/" is used for health checks
        application.add_route(
            path='/', route=lambda: JinaHealthModel(), methods=['GET']
        )

        return application


class NOWGateway(CompositeGateway):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.gateways = self.gateways[:1]
        # note order is important
        self._add_gateway(BFFGateway, self.ports[1], **kwargs)
        self._add_gateway(PlaygroundGateway, self.ports[2], **kwargs)

    def _add_gateway(self, gateway_cls, port, protocol='http', **kwargs):
        # ignore metrics_registry since it is not copyable
        runtime_args = self._deepcopy_with_ignore_attrs(
            self.runtime_args, ['metrics_registry']
        )
        runtime_args.port = [port]
        runtime_args.protocol = [protocol]
        gateway_kwargs = {k: v for k, v in kwargs.items() if k != 'runtime_args'}
        gateway_kwargs['runtime_args'] = dict(vars(runtime_args))
        gateway = gateway_cls(**gateway_kwargs)
        gateway.streamer = self.streamer
        self.gateways.insert(0, gateway)


if __name__ == '__main__':
    from jina import Flow

    os.environ['JINA_LOG_LEVEL'] = 'DEBUG'

    @dataclass
    class MMResult:
        title: Text
        desc: Text

    class DummyEncoder(Executor):
        @requests
        def foo(self, docs: DocumentArray, **kwargs):
            for index, doc in enumerate(docs):
                doc.matches = DocumentArray(
                    [
                        Document(
                            MMResult(
                                title=f'test title {index}: {i}',
                                desc=f'test desc {index}: {i}',
                            )
                        )
                        for i in range(10)
                    ]
                )
            return docs

    f = (
        Flow().config_gateway(
            # uses=f'jinahub+docker://2m00g87k/{NOW_GATEWAY_VERSION}',
            uses=NOWGateway,
            protocol=['http', 'http', 'http'],
            port=[8081, 8080, 8501],
            monitoring=True,
        )
        # .add(uses=DummyEncoder, name='encoder')
    )
    # f = Flow.load_config('/Users/joschkabraun/dev/jina_work/now/flow.yml')
    # f.to_k8s_yaml('tmp')

    with f:
        f.block()
        # print('start')
        # result = f.post(on='/search', inputs=Document(text='test'))
        # result.summary()
        # result[0].matches.summary()
        # result[0].matches[0].summary()

    # print('done')
