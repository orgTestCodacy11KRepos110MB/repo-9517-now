import json
import pathlib
import warnings

import docker
from kubernetes import client, config

from now.common.options import NEW_CLUSTER
from now.deployment.deployment import cmd
from now.log import time_profiler, yaspin_extended
from now.now_dataclasses import UserInput
from now.utils import sigmap

cur_dir = pathlib.Path(__file__).parent.resolve()
warnings.filterwarnings("ignore", category=DeprecationWarning)


def create_local_cluster(kind_path, **kwargs):
    out, err = cmd(f'{kind_path} get clusters')
    if err and 'No kind clusters' not in err.decode('utf-8'):
        print(err.decode('utf-8'))
        exit()
    cluster_name = 'jina-now'
    if cluster_name in out.decode('utf-8'):
        with yaspin_extended(
            sigmap=sigmap, text="Remove local cluster", color="green"
        ) as spinner:
            cmd(f'{kind_path} delete clusters {cluster_name}')
            spinner.ok('💀')

    with yaspin_extended(
        sigmap=sigmap, text="Setting up local cluster. ", color="green"
    ) as spinner:
        kindest_images = docker.from_env().images.list('kindest/node')
        if len(kindest_images) == 0:
            print(
                'Download kind image to set up local cluster - this might take a while :)'
            )
        _, err = cmd(
            f'{kind_path} create cluster --name {cluster_name} --config {cur_dir}/kind.yml',
        )
        if err and 'failed to create cluster' in err.decode('utf-8'):
            print('\n' + err.decode('utf-8').split('ERROR')[-1])
            exit(1)
        spinner.ok("📦")


def is_local_cluster(kubectl_path):
    command = f'{kubectl_path} get nodes -o json'
    out, error = cmd(f'{kubectl_path} get nodes -o json')
    try:
        out = json.loads(out)
    except:
        print(f'Command {command} gives the following error: {error.decode("utf-8")}')
        exit(1)
    addresses = out['items'][0]['status']['addresses']
    is_local = len([a for a in addresses if a['type'] == 'ExternalIP']) == 0
    return is_local


@time_profiler
def setup_cluster(
    user_input: UserInput,
    kubectl_path='kubectl',
    kind_path='kind',
    **kwargs,
):
    if user_input.cluster == NEW_CLUSTER['value']:
        create_local_cluster(kind_path, **kwargs)
    elif user_input.deployment_type != 'remote':
        cmd(f'{kubectl_path} config use-context {user_input.cluster}')
        ask_existing(kubectl_path)


def ask_existing(kubectl_path, **kwargs):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    if 'nowapi' in [item.metadata.name for item in v1.list_namespace().items]:
        with yaspin_extended(
            sigmap=sigmap, text="Remove old deployment", color="green"
        ) as spinner:
            cmd(f'{kubectl_path} delete ns nowapi')
            spinner.ok('💀')
