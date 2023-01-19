import os
from argparse import Namespace
from concurrent.futures import ProcessPoolExecutor

import boto3
import requests

from now.cli import cli
from now.constants import DatasetTypes
from now.demo_data import DEFAULT_EXAMPLE_HOSTED
from now.deployment.deployment import list_all_wolf, terminate_wolf


def upsert_cname_record(source, target):
    aws_client = boto3.client(
        'route53',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )
    try:
        aws_client.change_resource_record_sets(
            HostedZoneId=os.environ['AWS_HOSTED_ZONE_ID'],
            ChangeBatch={
                'Comment': 'add %s -> %s' % (source, target),
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': source,
                            'Type': 'CNAME',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': target}],
                        },
                    }
                ],
            },
        )
    except Exception as e:
        print(e)


def deploy(app_name, app_data):
    print(f'Deploying {app_name} app with data: {app_data}')
    NAMESPACE = f'examples-{app_name}-{app_data}'.replace('_', '-')
    kwargs = {
        'now': 'start',
        'app': app_name,
        'dataset_type': DatasetTypes.DEMO,
        'dataset_name': app_data,
        'proceed': True,
        'secured': False,
        'ns': NAMESPACE,
        'flow_name': NAMESPACE,
    }
    kwargs = Namespace(**kwargs)
    try:
        response_cli = cli(args=kwargs)
    except Exception as e:  # noqa E722
        response_cli = None
    # parse the response
    if response_cli:
        host_target_ = response_cli.get('host')
        if host_target_ and host_target_.startswith('grpcs://'):
            host_target_ = host_target_.replace('grpcs://', '')
            host_source = f'now-example-{app_name}-{app_data}.dev.jina.ai'.replace(
                '_', '-'
            )
            # update the CNAME entry in the Route53 records
            upsert_cname_record(host_source, host_target_)
        else:
            print(
                'No host returned starting with "grpcs://". Make sure Jina NOW returns host'
            )
    else:
        raise ValueError(f'Deployment failed for {app_name} and {app_data}. Re-run it')
    return response_cli


if __name__ == '__main__':
    os.environ['JINA_AUTH_TOKEN'] = os.environ.get('WOLF_TOKEN')
    os.environ['NOW_EXAMPLES'] = 'True'
    os.environ['JCLOUD_LOGLEVEL'] = 'DEBUG'
    deployment_type = os.environ.get('DEPLOYMENT_TYPE', 'partial').lower()
    to_deploy = set()

    if deployment_type == 'all':
        # List all deployments and delete them
        flows = list_all_wolf(namespace=None)
        flow_ids = [f['id'].replace('jflow-', '') for f in flows]
        with ProcessPoolExecutor() as thread_executor:
            # call delete function with each flow
            thread_executor.map(lambda x: terminate_wolf(x), flow_ids)
        print('Deploying all examples!!')
    else:
        # check if deployment is already running else add to deploy_list
        bff = 'https://nowrun.jina.ai/api/v1/admin/getStatus'
        for app, data in DEFAULT_EXAMPLE_HOSTED.items():
            for ds_name in data:
                host = f'grpcs://now-example-{app}-{ds_name}.dev.jina.ai'.replace(
                    '_', '-'
                )
                request_body = {
                    'host': host,
                    'jwt': {'token': os.environ['WOLF_TOKEN']},
                }
                resp = requests.post(bff, json=request_body)
                if resp.status_code != 200:
                    to_deploy.add((app, ds_name))
        print('Total Apps to re-deploy: ', len(to_deploy))

    results = []
    with ProcessPoolExecutor() as thread_executor:
        futures = []
        if deployment_type == 'all':
            # Create all new deployments and update CNAME records
            for app, data in DEFAULT_EXAMPLE_HOSTED.items():
                for ds_name in data:
                    f = thread_executor.submit(deploy, app, ds_name)
                    futures.append(f)
        else:
            for app, ds_name in to_deploy:
                # Create the failed deployments and update CNAME records
                f = thread_executor.submit(deploy, app, ds_name)
                futures.append(f)
        for f in futures:
            results.append(f.result())
    print(results)
