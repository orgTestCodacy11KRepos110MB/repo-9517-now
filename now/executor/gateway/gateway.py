import os

import streamlit.web.bootstrap
from jina import Gateway
from streamlit.web.server import Server as StreamlitServer
from uvicorn import Config
from uvicorn import Server as UvicornServer

from now.constants import CG_BFF_PORT
from now.executor.gateway.bff.app.app import application

cur_dir = os.path.dirname(__file__)


class NOWGateway(Gateway):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.streamlit_script = 'playground/playground.py'

    async def setup_server(self):
        streamlit.web.bootstrap._fix_sys_path(self.streamlit_script)
        streamlit.web.bootstrap._fix_matplotlib_crash()
        streamlit.web.bootstrap._fix_tornado_crash()
        streamlit.web.bootstrap._fix_sys_argv(self.streamlit_script, ())
        streamlit.web.bootstrap._fix_pydeck_mapbox_api_warning()
        streamlit.web.bootstrap._install_pages_watcher(self.streamlit_script)
        self.streamlit_server = StreamlitServer(
            os.path.join(cur_dir, self.streamlit_script),
            f'"python -m streamlit" run --browser.serverPort {self.port} {self.streamlit_script}',
        )

        self.uvicorn_server = UvicornServer(
            Config(application, host=self.host, port=CG_BFF_PORT)
        )

    async def run_server(self):
        await self.streamlit_server.start()
        streamlit.web.bootstrap._on_server_start(self.streamlit_server)
        streamlit.web.bootstrap._set_up_signal_handler(self.streamlit_server)
        await self.uvicorn_server.serve()

        await self.streamlit_server.stopped

    async def shutdown(self):
        self.streamlit_server.stop()

        self.uvicorn_server.should_exit = True
        await self.uvicorn_server.shutdown()


if __name__ == '__main__':
    from jina import Flow

    flow = Flow().config_gateway(
        uses=NOWGateway,
        port=12345,
        protocol='http',
    )

    with flow:
        flow.block()
