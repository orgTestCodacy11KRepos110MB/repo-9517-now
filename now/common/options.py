"""
This module implements a command-line dialog with the user.
Its goal is to configure a UserInput object with users specifications.
Optionally, values can be passed from the command-line when jina-now is launched. In that case,
the dialog won't ask for the value.
"""
from __future__ import annotations, print_function, unicode_literals

import importlib
import os

from hubble import AuthenticationRequiredError
from kubernetes import client, config

from now.constants import Apps, DatasetTypes
from now.deployment.deployment import cmd
from now.log import yaspin_extended
from now.now_dataclasses import DialogOptions, UserInput
from now.utils import (
    _get_context_names,
    get_info_hubble,
    jina_auth_login,
    sigmap,
    to_camel_case,
)

NEW_CLUSTER = {'name': '🐣 create new', 'value': 'new'}
AVAILABLE_SOON = 'will be available in upcoming versions'

# Make sure you add this dialog option to your app in order of dependency, i.e., if some dialog option depends on other
# then the parent should be called first before the dependant can called.

APP = DialogOptions(
    name='app',
    choices=[
        {
            'name': '📝 ▶ 🏞 text to image search',
            'value': Apps.TEXT_TO_IMAGE,
        },
        {
            'name': '🏞 ▶ 📝 image to text search',
            'value': Apps.IMAGE_TO_TEXT,
        },
        {
            'name': '🏞 ▶ 🏞 image to image search',
            'value': Apps.IMAGE_TO_IMAGE,
        },
        {'name': '📝 ▶ 📝 text to text search', 'value': Apps.TEXT_TO_TEXT},
        {
            'name': '📝 ▶ 🎦 text to video search (gif only at the moment)',
            'value': Apps.TEXT_TO_VIDEO,
        },
        {
            'name': '🥁 ▶ 🥁 music to music search',
            'value': Apps.MUSIC_TO_MUSIC,
        },
        {
            'name': '📝 ▶ 📝+🏞 text to text+image search',
            'value': Apps.TEXT_TO_TEXT_AND_IMAGE,
            'disabled': AVAILABLE_SOON,
        },
    ],
    prompt_message='What sort of search engine would you like to build?',
    prompt_type='list',
    is_terminal_command=True,
    description='What sort of search engine would you like to build?',
)

DATASET_TYPE = DialogOptions(
    name='dataset_type',
    prompt_message='How do you want to provide input? (format: https://docarray.jina.ai/)',
    choices=[
        {'name': 'Demo dataset', 'value': DatasetTypes.DEMO},
        {
            'name': 'DocArray name (recommended)',
            'value': DatasetTypes.DOCARRAY,
        },
        {
            'name': 'DocArray URL',
            'value': DatasetTypes.URL,
        },
        {
            'name': 'Local path',
            'value': DatasetTypes.PATH,
        },
        {
            'name': 'S3 bucket',
            'value': DatasetTypes.S3_BUCKET,
        },
        {
            'name': 'Elasticsearch',
            'value': DatasetTypes.ELASTICSEARCH,
            'disabled': AVAILABLE_SOON,
        },
    ],
    prompt_type='list',
    is_terminal_command=True
    # post_func=lambda user_input, **kwargs: _parse_custom_data_from_cli(
    #     user_input, **kwargs
    # ),
)

DEMO_DATA = DialogOptions(
    name='dataset_name',
    prompt_message='What demo dataset do you want to use?',
    choices=lambda user_input, **kwargs: [
        {'name': demo_data.display_name, 'value': demo_data.name}
        for demo_data in user_input.app_instance.demo_datasets
    ],
    prompt_type='list',
    depends_on=DATASET_TYPE,
    is_terminal_command=True,
    description='Select one of the available demo datasets',
    conditional_check=lambda user_input, **kwargs: user_input.dataset_type
    == DatasetTypes.DEMO,
)

DOCARRAY_NAME = DialogOptions(
    name='dataset_name',
    prompt_message='Please enter your DocArray name:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.DOCARRAY,
)

DATASET_URL = DialogOptions(
    name='dataset_url',
    prompt_message='Please paste in the URL to download your DocArray from:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    is_terminal_command=True,
    conditional_check=lambda user_input: user_input.dataset_type == DatasetTypes.URL,
)

DATASET_PATH = DialogOptions(
    name='dataset_path',
    prompt_message='Please enter the path to the local folder:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    is_terminal_command=True,
    conditional_check=lambda user_input: user_input.dataset_type == DatasetTypes.PATH,
)

DATASET_PATH_S3 = DialogOptions(
    name='dataset_path',
    prompt_message='Please enter the S3 URI to the folder:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.S3_BUCKET,
)

AWS_ACCESS_KEY_ID = DialogOptions(
    name='aws_access_key_id',
    prompt_message='Please enter the AWS access key ID:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.S3_BUCKET,
)

AWS_SECRET_ACCESS_KEY = DialogOptions(
    name='aws_secret_access_key',
    prompt_message='Please enter the AWS secret access key:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.S3_BUCKET,
)

AWS_REGION_NAME = DialogOptions(
    name='aws_region_name',
    prompt_message='Please enter the AWS region:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.S3_BUCKET,
)

# --------------------------------------------- #

SEARCH_FIELDS = DialogOptions(
    name='search_fields',
    prompt_message='Enter comma-separated search fields:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.data == 'custom',
    post_func=lambda user_input, **kwargs: _parse_search_fields(user_input),
)


def _parse_search_fields(user_input: UserInput):
    user_input.search_fields = [
        field.strip() for field in user_input.search_fields.split(',')
    ]


FILTER_FIELDS = DialogOptions(
    name='filter_fields',
    prompt_message='Enter comma-separated filter fields:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.data == 'custom',
    post_func=lambda user_input, **kwargs: _parse_filter_fields(user_input),
)


def _parse_filter_fields(user_input: UserInput):
    user_input.filter_fields = [
        field.strip() for field in user_input.filter_fields.split(',')
    ]


ES_INDEX_NAME = DialogOptions(
    name='es_index_name',
    prompt_message='Please enter the name of your Elasticsearch index:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.ELASTICSEARCH,
)

ES_HOST_NAME = DialogOptions(
    name='es_host_name',
    prompt_message='Please enter the address of your Elasticsearch node:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.ELASTICSEARCH,
)

ES_ADDITIONAL_ARGS = DialogOptions(
    name='es_additional_args',
    prompt_message='Please enter additional arguments for your Elasticsearch node if there are any:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.ELASTICSEARCH,
)

# --------------------------------------------- #

DEPLOYMENT_TYPE = DialogOptions(
    name='deployment_type',
    prompt_message='Where do you want to deploy your search engine?',
    prompt_type='list',
    choices=[
        {
            'name': '⛅️ Jina Cloud',
            'value': 'remote',
        },
        {
            'name': '📍 Local',
            'value': 'local',
        },
    ],
    is_terminal_command=True,
    description='Option is `local` and `remote`. Select `local` if you want search engine to be deployed on local '
    'cluster. Select `remote` to deploy it on Jina Cloud',
    post_func=lambda user_input, **kwargs: _jina_auth_login(user_input, **kwargs),
)

LOCAL_CLUSTER = DialogOptions(
    name='cluster',
    prompt_message='On which cluster do you want to deploy your search engine?',
    prompt_type='list',
    choices=lambda user_input, **kwargs: _construct_local_cluster_choices(
        user_input, **kwargs
    ),
    depends_on=DEPLOYMENT_TYPE,
    is_terminal_command=True,
    description='Reference an existing `local` cluster or select `new` to create a new one. '
    'Use this only when the `--deployment-type=local`',
    conditional_check=lambda user_inp: user_inp.deployment_type == 'local',
    post_func=lambda user_input, **kwargs: user_input.app_instance.run_checks(
        user_input
    ),
)

PROCEED = DialogOptions(
    name='proceed',
    prompt_message='jina-now is deployed already. Do you want to remove the current data?',
    prompt_type='list',
    choices=[
        {'name': '⛔ no', 'value': False},
        {'name': '✅ yes', 'value': True},
    ],
    depends_on=LOCAL_CLUSTER,
    conditional_check=lambda user_input: _check_if_namespace_exist(),
)

SECURED = DialogOptions(
    name='secured',
    prompt_message='Do you want to secure the flow?',
    prompt_type='list',
    choices=[
        {'name': '✅ yes', 'value': True},
        {'name': '⛔ no', 'value': False},
    ],
    depends_on=DEPLOYMENT_TYPE,
    conditional_check=lambda user_inp: user_inp.deployment_type == 'remote',
)

ADDITIONAL_USERS = DialogOptions(
    name='additional_user',
    prompt_message='Do you want to provide additional users access to this flow?',
    prompt_type='list',
    choices=[
        {'name': '✅ yes', 'value': True},
        {'name': '⛔ no', 'value': False},
    ],
    depends_on=SECURED,
    conditional_check=lambda user_inp: user_inp.secured,
)

USER_EMAILS = DialogOptions(
    name='user_emails',
    prompt_message='Please enter the comma separated Email IDs '
    'who will have access to this flow:',
    prompt_type='input',
    depends_on=ADDITIONAL_USERS,
    conditional_check=lambda user_inp: user_inp.additional_user,
    post_func=lambda user_input, **kwargs: _add_additional_users(user_input, **kwargs),
)


def _add_additional_users(user_input: UserInput, **kwargs):
    user_input.user_emails = (
        [email.strip() for email in kwargs['user_emails'].split(',')]
        if kwargs['user_emails']
        else []
    )


def _check_if_namespace_exist():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    return 'nowapi' in [item.metadata.name for item in v1.list_namespace().items]


def construct_app(app_name: str):
    return getattr(
        importlib.import_module(f'now.app.{app_name}.app'),
        f'{to_camel_case(app_name)}',
    )()


def _jina_auth_login(user_input, **kwargs):
    if user_input.deployment_type != 'remote':
        return

    try:
        jina_auth_login()
    except AuthenticationRequiredError:
        with yaspin_extended(
            sigmap=sigmap, text='Log in to JCloud', color='green'
        ) as spinner:
            cmd('jina auth login')
        spinner.ok('🛠️')

    get_info_hubble(user_input)
    os.environ['JCLOUD_NO_SURVEY'] = '1'


def _construct_local_cluster_choices(user_input, **kwargs):
    active_context = kwargs.get('active_context')
    contexts = kwargs.get('contexts')
    context_names = _get_context_names(contexts, active_context)
    choices = [NEW_CLUSTER]
    # filter contexts with `gke`
    if len(context_names) > 0 and len(context_names[0]) > 0:
        context_names = [
            context
            for context in context_names
            if 'gke' not in context and _cluster_running(context)
        ]
        choices = context_names + choices
    return choices


def _cluster_running(cluster):
    config.load_kube_config(context=cluster)
    v1 = client.CoreV1Api()
    try:
        v1.list_namespace()
    except Exception as e:
        return False
    return True


# def _parse_custom_data_from_cli(user_input: UserInput, **kwargs) -> None:
#     data = user_input.data
#     if data == 'custom':
#         return
#
#     app_instance = user_input.app_instance
#     for k, v in enumerate(AVAILABLE_DATASET[app_instance.output_modality]):
#         if v[0] == data:
#             return
#
#     try:
#         data = os.path.expanduser(data)
#     except Exception:
#         pass
#     if os.path.exists(data):
#         user_input.dataset_type = DatasetTypes.PATH
#         user_input.dataset_path = data
#     elif 'http' in data:
#         user_input.dataset_type = DatasetTypes.URL
#         user_input.dataset_url = data
#     else:
#         user_input.dataset_type = DatasetTypes.DOCARRAY
#         user_input.dataset_name = data


data_type = [DATASET_TYPE]
data_fields = [SEARCH_FIELDS, FILTER_FIELDS]
data_demo = [DEMO_DATA]
data_da = [DOCARRAY_NAME, DATASET_PATH, DATASET_URL]
data_s3 = [DATASET_PATH_S3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME]
data_es = [
    ES_HOST_NAME,
    ES_INDEX_NAME,
    ES_ADDITIONAL_ARGS,
]
cluster = [DEPLOYMENT_TYPE, LOCAL_CLUSTER]
remote_cluster = [SECURED, ADDITIONAL_USERS, USER_EMAILS]


base_options = (
    data_type
    + data_demo
    + data_da
    + data_s3
    + data_es
    + data_fields
    + cluster
    + remote_cluster
)
