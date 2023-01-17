import logging
import os
import tempfile
import time
import hubble
import json
from argparse import Namespace
import pytest
from pytest_mock import MockerFixture

from now.utils import get_flow_id
from now.deployment.deployment import terminate_wolf
from now.cli import cli

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class HubbleAuthPatch:
    @staticmethod
    async def login():
        pass

    @staticmethod
    def get_auth_token() -> str:
        token = os.environ.get('WOLF_TOKEN')
        if token:
            log.debug(f'Found token in env *** (Len={len(token)})')
            return token
        else:
            raise RuntimeError(
                'WOLF token not found in environment under key `WOLF_TOKEN`'
            )


@pytest.fixture
def with_hubble_login_patch(mocker: MockerFixture) -> None:
    # WOLF token is required for deployment, but not set locally (only in the CI)
    # If you are running this locally, the WOLF_TOKEN env variable will be set using hubble
    # Otherwise, it will be set in the CI.
    if 'WOLF_TOKEN' not in os.environ:
        hubble.login()
        os.environ['WOLF_TOKEN'] = hubble.Auth.get_auth_token()


@pytest.fixture()
def cleanup(deployment_type, dataset):
    with tempfile.TemporaryDirectory() as tmpdir:
        start = time.time()
        yield tmpdir
        print('start cleanup')
        try:
            if deployment_type == 'remote':
                with open(f'{tmpdir}/flow_details.json', 'r') as f:
                    flow_details = json.load(f)
                if 'host' not in flow_details:
                    print('nothing to clean up')
                    return
                host = flow_details['host']
                flow_id = get_flow_id(host)
                terminate_wolf(flow_id)
            else:
                print('\nDeleting local cluster')
                kwargs = {
                    'deployment_type': deployment_type,
                    'now': 'stop',
                    'cluster': 'kind-jina-now',
                    'delete-cluster': True,
                }
                kwargs = Namespace(**kwargs)
                cli(args=kwargs)
        except Exception as e:
            print('no clean up')
            print(e)
            return
        print('cleaned up')
        now = time.time() - start
        mins = int(now / 60)
        secs = int(now % 60)
        print(50 * '#')
        print(
            f'Time taken to execute `{deployment_type}` deployment with dataset `{dataset}`: {mins}m {secs}s'
        )
        print(50 * '#')
