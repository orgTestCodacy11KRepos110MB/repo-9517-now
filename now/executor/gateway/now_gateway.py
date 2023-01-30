import os
from time import sleep

import streamlit.web.bootstrap
from docarray import Document
from jina import Gateway
from jina.serve.runtimes.gateway import CompositeGateway
from jina.serve.runtimes.gateway.http.fastapi import FastAPIBaseGateway
from jina.serve.runtimes.gateway.http.models import JinaHealthModel
from streamlit.web.server import Server as StreamlitServer

from now.constants import CG_BFF_PORT
from now.deployment.deployment import cmd
from now.executor.gateway.bff.app.app import application

cur_dir = os.path.dirname(__file__)


class PlaygroundGateway(Gateway):
    def __init__(self, secured: bool, **kwargs):
        super().__init__(**kwargs)
        # need to get it through kwargs
        # self.secured = kwargs.get('secured', False)
        self.secured = secured
        self.streamlit_script = 'playground/playground.py'

    async def setup_server(self):
        streamlit.web.bootstrap._fix_sys_path(self.streamlit_script)
        streamlit.web.bootstrap._fix_matplotlib_crash()
        streamlit.web.bootstrap._fix_tornado_crash()
        streamlit.web.bootstrap._fix_sys_argv(self.streamlit_script, ())
        streamlit.web.bootstrap._fix_pydeck_mapbox_api_warning()
        # streamlit.web.bootstrap._install_pages_watcher(self.streamlit_script)
        streamlit_cmd = (
            f'"python -m streamlit" run --browser.serverPort 12983 {self.streamlit_script} --server.address=0.0.0.0 '
            f'--server.baseUrlPath /playground '
        )
        if self.secured:
            streamlit_cmd += '-- --secured'
        self.streamlit_server = StreamlitServer(
            os.path.join(cur_dir, self.streamlit_script), streamlit_cmd
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
    def __init__(self, secured: bool, **kwargs):
        # need to update port ot 8082, as nginx will listen on 8081
        kwargs['runtime_args']['port'] = [8082]
        super().__init__(**kwargs)

        # note order is important
        self._add_gateway(BFFGateway, CG_BFF_PORT, **kwargs)
        self._add_gateway(PlaygroundGateway, 8501, **{'secured': secured, **kwargs})
        # self._add_gateway(PlaygroundGateway, 8501, secured,  **kwargs)

        self.setup_nginx()

    async def shutdown(self):
        await super().shutdown()
        self.shutdown_nginx()

    def setup_nginx(self):
        output, error = cmd(
            [
                'nginx',
                '-c',
                os.path.join(cur_dir, '', 'nginx.conf'),
            ]
        )
        sleep(10)
        self.logger.info('Nginx started')
        self.logger.info(f'nginx output: {output}')
        self.logger.info(f'nginx error: {error}')

    def shutdown_nginx(self):
        output, error = cmd(['nginx', '-s', 'stop'])
        self.logger.info('Nginx stopped')
        self.logger.info(f'nginx output: {output}')
        self.logger.info(f'nginx error: {error}')

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

    # class DummyEncoder(Executor):
    #     @requests
    #     def foo(self, docs: DocumentArray, **kwargs):
    #         for index, doc in enumerate(docs):
    #             doc.matches = DocumentArray(
    #                 [
    #                     Document(
    #                         MMResult(
    #                             title=f'test title {index}: {i}',
    #                             desc=f'test desc {index}: {i}',
    #                         )
    #                     )
    #                     for i in range(10)
    #                 ]
    #             )
    #         return docs

    f = (
        Flow().config_gateway(
            # uses=f'jinahub+docker://q4x2gadu/0.0.32',
            uses=NOWGateway,
            protocol=['http'],
            port=[8081],
            env={'JINA_LOG_LEVEL': 'DEBUG'},
            uses_with={'secured': False},
        )
        # .add(
        #     uses=DummyEncoder,
        #     env={'JINA_LOG_LEVEL': 'DEBUG'},
        # )
        # .add(
        #     name='autocomplete',
        #     uses='jinahub+docker://w5w084h7/0.0.9-fix-filter-index-fields-20',
        #     env={'JINA_LOG_LEVEL': 'DEBUG'},
        # )
        .add(
            name='preprocessor',
            uses='jinahub+docker://2hgojz3z/0.0.121-refactor-custom-gateway-47',
            env={'JINA_LOG_LEVEL': 'DEBUG'},
        )
        # .add(
        #     host=EXTERNAL_CLIP_HOST,
        #     port=443,
        #     tls=True,
        #     external=True,
        #     name='clip',
        #     env={'JINA_LOG_LEVEL': 'DEBUG'},
        # )
    )
    # f = Flow.load_config('/Users/joschkabraun/dev/now/flow.yml')

    with f:
        # f.block()
        sleep(10)
        print('start')
        result = f.post(on='/search', inputs=Document(text='test'))
        result.summary()
        result[0].matches.summary()
        result[0].matches[0].summary()

    print('done')
