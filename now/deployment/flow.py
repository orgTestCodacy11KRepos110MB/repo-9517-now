import os.path
import tempfile
from typing import Dict
from jina.clients import Client
from now.deployment.deployment import deploy_wolf
from now.log import time_profiler
from now.utils import write_env_file, write_flow_file


@time_profiler
def deploy_flow(
    flow_yaml: str,
    env_dict: Dict,
):
    """Deploy a Flow on JCloud, Kubernetes, or using Jina Orchestration"""
    # TODO create tmpdir top level and pass it down
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, 'dot.env')
        write_env_file(env_file, env_dict)

        # hack we don't know if the flow yaml is a path or a string
        if type(flow_yaml) == dict:
            flow_file = os.path.join(tmpdir, 'flow.yml')
            write_flow_file(flow_yaml, flow_file)
            flow_yaml = flow_file

        flow = deploy_wolf(path=flow_yaml)
        host = flow.endpoints['gateway']
        client = Client(host=host)

        # host & port
        gateway_port = None
        gateway_host_internal = host

        if os.path.exists(env_file):
            os.remove(env_file)
    return (
        client,
        gateway_port,
        gateway_host_internal,
    )
