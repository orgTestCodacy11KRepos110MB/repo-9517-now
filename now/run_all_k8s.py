import os

import cowsay
import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Column, Table

from now import run_backend, run_bff_playground
from now.cloud_manager import setup_cluster
from now.constants import DOCKER_BFF_PLAYGROUND_TAG, FLOW_STATUS, DatasetTypes
from now.deployment.deployment import cmd, list_all_wolf, status_wolf, terminate_wolf
from now.dialog import configure_user_input
from now.log import yaspin_extended
from now.utils import _get_context_names, maybe_prompt_user, sigmap


def stop_now(contexts, active_context, **kwargs):
    choices = _get_context_names(contexts, active_context)
    # Add all remote Flows that exists with the namespace `nowapi`
    alive_flows = list_all_wolf(status=FLOW_STATUS)
    for flow_details in alive_flows:
        choices.append(flow_details['name'])
    if len(choices) == 0:
        cowsay.cow('nothing to stop')
        return
    else:
        questions = [
            {
                'type': 'list',
                'name': 'cluster',
                'message': 'Which cluster do you want to delete?',
                'choices': choices,
            }
        ]
        cluster = maybe_prompt_user(questions, 'cluster', **kwargs)
    if cluster == 'kind-jina-now':
        delete_cluster = maybe_prompt_user(
            [
                {
                    'type': 'list',
                    'name': 'delete-cluster',
                    'message': 'Do you want to delete the entire cluster or just the namespace?',
                    'choices': [
                        {'name': '⛔ no, keep the cluster', 'value': False},
                        {'name': '✅ yes, delete everything', 'value': True},
                    ],
                }
            ],
            attribute='delete-cluster',
            **kwargs,
        )
        if delete_cluster:
            with yaspin_extended(
                sigmap=sigmap, text=f"Remove local cluster {cluster}", color="green"
            ) as spinner:
                cmd(f'{kwargs["kind_path"]} delete clusters jina-now')
                spinner.ok('💀')
            cowsay.cow('local jina NOW cluster removed')
        else:
            with yaspin_extended(
                sigmap=sigmap,
                text=f"Remove namespace nowapi NOW from {cluster}",
                color="green",
            ) as spinner:
                cmd(f'{kwargs["kubectl_path"]} delete ns nowapi')
                spinner.ok('💀')
            cowsay.cow(f'nowapi namespace removed from {cluster}')
    elif 'wolf.jina.ai' in cluster:
        flow = [x for x in alive_flows if x['name'] == cluster][0]
        flow_id = flow['id']
        _result = status_wolf(flow_id)
        if _result is None:
            print(f'❎ Flow not found in JCloud. Likely, it has been deleted already')
        if _result is not None and _result['status']['phase'] == FLOW_STATUS:
            terminate_wolf(flow_id)
            from hubble import Client

            cookies = {'st': Client().token}
            requests.delete(
                f'https://storefrontapi.nowrun.jina.ai/api/v1/schedule_sync/{flow_id}',
                cookies=cookies,
            )
        cowsay.cow(f'remote Flow `{cluster}` removed')
    else:
        with yaspin_extended(
            sigmap=sigmap, text=f"Remove jina NOW from {cluster}", color="green"
        ) as spinner:
            cmd(f'{kwargs["kubectl_path"]} delete ns nowapi')
            spinner.ok('💀')
        cowsay.cow(f'nowapi namespace removed from {cluster}')


def start_now(**kwargs):
    user_input = configure_user_input(**kwargs)
    app_instance = user_input.app_instance
    # Only if the deployment is remote and the demo examples is available for the selected app
    # Should not be triggered for CI tests
    if app_instance.is_demo_available(user_input):
        gateway_host = 'remote'
        gateway_host_internal = f'grpcs://now-example-{app_instance.app_name}-{user_input.dataset_name}.dev.jina.ai'.replace(
            '_', '-'
        )
        gateway_port_internal = None
    else:
        if not os.environ.get('NOW_TESTING', False):
            setup_cluster(user_input, **kwargs)
        (
            gateway_host,
            gateway_port,
            gateway_host_internal,
            gateway_port_internal,
        ) = run_backend.run(app_instance, user_input, **kwargs)

    if os.environ.get('NOW_TESTING', False):
        # start_bff(9090, daemon=True)
        # sleep(10)
        bff_playground_host = 'http://localhost'
        bff_port = '9090'
        playground_port = '80'
    elif gateway_host == 'localhost' or 'NOW_CI_RUN' in os.environ:
        # only deploy playground when running locally or when testing
        bff_playground_host, bff_port, playground_port = run_bff_playground.run(
            gateway_host=gateway_host,
            docker_bff_playground_tag=DOCKER_BFF_PLAYGROUND_TAG,
            kubectl_path=kwargs['kubectl_path'],
        )
    else:
        bff_playground_host = 'https://nowrun.jina.ai'
        bff_port = '80'
        playground_port = '80'
    # TODO: add separate BFF endpoints in print output
    bff_url = (
        bff_playground_host
        + ('' if str(bff_port) == '80' else f':{bff_port}')
        + f'/api/v1/search-app/docs'
    )
    playground_url = (
        bff_playground_host
        + ('' if str(playground_port) == '80' else f':{playground_port}')
        + (
            f'/?host='
            + (gateway_host_internal if gateway_host != 'localhost' else 'gateway')
            + (
                f'&data={user_input.dataset_name if user_input.dataset_type == DatasetTypes.DEMO else "custom"}'
            )
            + (f'&secured={user_input.secured}' if user_input.secured else '')
        )
        + (f'&port={gateway_port_internal}' if gateway_port_internal else '')
    )
    print()
    my_table = Table(
        'Attribute',
        Column(header="Value", overflow="fold"),
        show_header=False,
        box=box.SIMPLE,
        highlight=True,
    )
    my_table.add_row('Api docs', bff_url)
    if user_input.secured and user_input.api_key:
        my_table.add_row('API Key', user_input.api_key)
    my_table.add_row('Playground', playground_url)
    console = Console()
    console.print(
        Panel(
            my_table,
            title=f':tada: Search app is NOW ready!',
            expand=False,
        )
    )
    return {
        'bff': bff_url,
        'playground': playground_url,
        'bff_playground_host': bff_playground_host,
        'bff_port': bff_port,
        'playground_port': playground_port,
        'host': gateway_host_internal,
        'port': gateway_port_internal,
        'secured': user_input.secured,
    }
