import os
from argparse import Namespace

from now.cli import cli
from now.constants import Apps, DatasetTypes

os.environ['JCLOUD_LOGLEVEL'] = 'DEBUG'


def deploy():
    kwargs = {
        'now': 'start',
        'app': Apps.SEARCH_APP,
        'dataset_type': DatasetTypes.S3_BUCKET,
        'dataset_path': '',
        'aws_access_key_id': '',
        'aws_secret_access_key': '',
        'aws_region_name': '',
        'secured': True,
        'additional_user': True,
        'user_emails': [],
    }
    kwargs = Namespace(**kwargs)
    response = cli(args=kwargs)
    return response


if __name__ == '__main__':
    result = deploy()
    print(result)
