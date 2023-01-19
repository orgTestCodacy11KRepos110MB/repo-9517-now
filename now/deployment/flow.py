import os.path
import pathlib
import tempfile
from multiprocessing import Process
from time import sleep
from typing import Dict

from jina import Flow
from jina.clients import Client
from kubernetes import client as k8s_client
from kubernetes import config
from now.constants import DEFAULT_FLOW_NAME
from now.deployment.deployment import deploy_wolf
from now.log import time_profiler
from now.utils import write_env_file, write_flow_file

cur_dir = pathlib.Path(__file__).parent.resolve()
MAX_WAIT_TIME = 1800


def batch(data_list, n=1):
    l = len(data_list)
    for ndx in range(0, l, n):
        yield data_list[ndx : min(ndx + n, l)]


def wait_for_lb(lb_name, ns):
    config.load_kube_config()
    v1 = k8s_client.CoreV1Api()
    while True:
        try:
            services = v1.list_namespaced_service(namespace=ns)
            ip = [
                s.status.load_balancer.ingress[0].ip
                for s in services.items
                if s.metadata.name == lb_name
            ][0]
            if ip:
                break
        except Exception:
            pass
        sleep(1)
    return ip


def check_pods_health(ns):
    config.load_kube_config()
    v1 = k8s_client.CoreV1Api()
    pods = v1.list_namespaced_pod(ns).items

    for pod in pods:
        try:
            message = pod.status.container_statuses[0].state.waiting.message
        except:
            message = None

        if message and 'Error' in message:
            raise Exception(pod.metadata.name + " " + message)


def wait_for_flow(client, ns):
    wait_time = 0
    while not client.is_flow_ready() and wait_time <= MAX_WAIT_TIME:
        if 'NOW_TESTING' not in os.environ:
            check_pods_health(ns)
        wait_time += 1
        sleep(1)
    if not client.is_flow_ready():
        raise Exception('Flow execution timed out.')


def start_flow_in_process(f):
    def start_flow():
        with f:
            print('flow started in process')
            f.block()

    p1 = Process(target=start_flow, args=())
    p1.daemon = False
    p1.start()


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

        if os.environ.get('NOW_TESTING', False):
            from dotenv import load_dotenv

            load_dotenv(env_file, override=True)

            f = Flow.load_config(flow_yaml)
            f.gateway_args.timeout_send = -1
            start_flow_in_process(f)

            host = 'localhost'
            client = Client(host=host, port=8080)
            wait_for_flow(client, DEFAULT_FLOW_NAME)
            # host & port
            gateway_port = 8080
            gateway_host_internal = host

        else:
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
