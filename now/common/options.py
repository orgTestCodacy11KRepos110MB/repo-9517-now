"""
This module implements a command-line dialog with the user.
Its goal is to configure a UserInput object with users specifications.
Optionally, values can be passed from the command-line when jina-now is launched. In that case,
the dialog won't ask for the value.
"""
from __future__ import annotations, print_function, unicode_literals

import importlib
import os
import uuid

from hubble import AuthenticationRequiredError
from now.common.detect_schema import (
    set_field_names_elasticsearch,
    set_field_names_from_docarray,
    set_field_names_from_local_folder,
    set_field_names_from_s3_bucket,
)
from now.constants import DatasetTypes
from now.deployment.deployment import cmd
from now.log import yaspin_extended
from now.now_dataclasses import DialogOptions, UserInput
from now.utils import (
    RetryException,
    get_info_hubble,
    jina_auth_login,
    sigmap,
    to_camel_case,
)

AVAILABLE_SOON = 'will be available in upcoming versions'


# Make sure you add this dialog option to your app in order of dependency, i.e., if some dialog option depends on other
# than the parent should be called first before the dependant can called.


def _check_index_field(user_input: UserInput, **kwargs):
    if not user_input.index_fields:
        raise RetryException('Please select at least one index field')

    if (
        user_input.index_fields[0]
        not in user_input.index_field_candidates_to_modalities.keys()
    ):
        raise ValueError(
            f'Index field specified is not among the index candidate fields. Please '
            f'choose one of the following: {user_input.index_field_candidates_to_modalities.keys()}'
        )


def _fill_filter_field_if_selected_all(user_input: UserInput, **kwargs):
    if '__all__' in user_input.filter_fields:
        user_input.filter_fields = list(
            user_input.filter_field_candidates_to_modalities.keys()
        )


def _append_all_option_to_filter(user_input: UserInput):
    choices = [
        {'name': field, 'value': field}
        for field in user_input.filter_field_candidates_to_modalities.keys()
        if field not in user_input.index_fields
    ]
    if len(choices) > 1:
        choices.append({'name': 'All of the above', 'value': '__all__'})
    return choices


APP_NAME = DialogOptions(
    name='flow_name',
    prompt_message='Choose a name for your application:',
    prompt_type='input',
    is_terminal_command=True,
    post_func=lambda user_input, **kwargs: clean_flow_name(user_input),
)


def clean_flow_name(user_input: UserInput):
    """
    Clean the flow name to make it valid, removing special characters and spaces.
    """
    user_input.flow_name = ''.join(
        [c for c in user_input.flow_name or '' if c.isalnum() or c == '-']
    ).lower()


DATASET_TYPE = DialogOptions(
    name='dataset_type',
    prompt_message='How do you want to provide input? (format: https://docarray.jina.ai/)',
    choices=[
        {'name': 'Demo dataset', 'value': DatasetTypes.DEMO},
        {
            'name': 'DocumentArray name (recommended)',
            'value': DatasetTypes.DOCARRAY,
        },
        {
            'name': 'Local folder',
            'value': DatasetTypes.PATH,
        },
        {
            'name': 'S3 bucket',
            'value': DatasetTypes.S3_BUCKET,
        },
        {
            'name': 'Elasticsearch',
            'value': DatasetTypes.ELASTICSEARCH,
        },
    ],
    prompt_type='list',
    is_terminal_command=True,
    post_func=lambda user_input, **kwargs: check_login_dataset(user_input),
)


def check_login_dataset(user_input: UserInput):
    if (
        user_input.dataset_type in [DatasetTypes.DEMO, DatasetTypes.DOCARRAY]
        and user_input.jwt is None
    ):
        _jina_auth_login(user_input)


def _get_demo_data_choices(user_input: UserInput, **kwargs):
    all_demo_datasets = []
    for demo_datasets in user_input.app_instance.demo_datasets.values():
        all_demo_datasets.extend(demo_datasets)
    return [
        {'name': demo_data.display_name, 'value': demo_data.name}
        for demo_data in all_demo_datasets
    ]


DEMO_DATA = DialogOptions(
    name='dataset_name',
    prompt_message='What demo dataset do you want to use?',
    choices=lambda user_input, **kwargs: _get_demo_data_choices(user_input),
    prompt_type='list',
    depends_on=DATASET_TYPE,
    is_terminal_command=True,
    description='Select one of the available demo datasets',
    conditional_check=lambda user_input, **kwargs: user_input.dataset_type
    == DatasetTypes.DEMO,
    post_func=lambda user_input, **kwargs: set_field_names_from_docarray(user_input),
)

DOCARRAY_NAME = DialogOptions(
    name='dataset_name',
    prompt_message='Please enter your DocArray name:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.dataset_type
    == DatasetTypes.DOCARRAY,
    post_func=lambda user_input, **kwargs: set_field_names_from_docarray(user_input),
)

DATASET_PATH = DialogOptions(
    name='dataset_path',
    prompt_message='Please enter the path to the local folder:',
    prompt_type='input',
    depends_on=DATASET_TYPE,
    is_terminal_command=True,
    conditional_check=lambda user_input: user_input.dataset_type == DatasetTypes.PATH,
    post_func=lambda user_input, **kwargs: set_field_names_from_local_folder(
        user_input
    ),
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
    post_func=lambda user_input, **kwargs: set_field_names_from_s3_bucket(user_input),
)

# --------------------------------------------- #


INDEX_FIELDS = DialogOptions(
    name='index_fields',
    choices=lambda user_input, **kwargs: [
        {'name': field, 'value': field}
        for field in user_input.index_field_candidates_to_modalities.keys()
    ],
    prompt_message='Please select the index fields:',
    prompt_type='checkbox',
    is_terminal_command=True,
    post_func=_check_index_field,
    argparse_kwargs={
        'type': lambda fields: fields.split(',') if fields else UserInput().index_fields
    },
)

FILTER_FIELDS = DialogOptions(
    name='filter_fields',
    choices=lambda user_input, **kwargs: _append_all_option_to_filter(user_input),
    prompt_message='Please select the filter fields',
    prompt_type='checkbox',
    depends_on=DATASET_TYPE,
    conditional_check=lambda user_input: user_input.filter_field_candidates_to_modalities
    is not None
    and len(
        set(user_input.filter_field_candidates_to_modalities.keys())
        - set(user_input.index_fields)
    )
    > 0,
    post_func=_fill_filter_field_if_selected_all,
)


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
    post_func=lambda user_input, **kwargs: set_field_names_elasticsearch(user_input),
)

# --------------------------------------------- #
SECURED = DialogOptions(
    name='secured',
    prompt_message='Do you want to secure the Flow?',
    prompt_type='list',
    choices=[
        {'name': '⛔ no', 'value': False},
        {'name': '✅ yes', 'value': True},
    ],
    is_terminal_command=True,
    post_func=lambda user_input, **kwargs: check_login_deployment(user_input),
)


def check_login_deployment(user_input: UserInput):
    if user_input.jwt is None:
        _jina_auth_login(user_input)


API_KEY = DialogOptions(
    name='api_key',
    prompt_message='Do you want to generate an API key to access this deployment?',
    prompt_type='list',
    choices=[
        {'name': '✅ yes', 'value': uuid.uuid4().hex},
        {'name': '⛔ no', 'value': False},
    ],
    depends_on=SECURED,
    is_terminal_command=True,
    description='Pass an API key to access the Flow once the deployment is complete. ',
    conditional_check=lambda user_inp: str(user_inp.secured).lower() == 'true',
    post_func=lambda user_input, **kwargs: _set_value_to_none(user_input),
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
    conditional_check=lambda user_inp: str(user_inp.secured).lower() == 'true',
)

USER_EMAILS = DialogOptions(
    name='user_emails',
    prompt_message='Please enter email addresses (separated by commas) '
    'to grant access to this Flow.\nAdditionally, you can specify comma-separated domain names'
    ' such that all users from that domain can access this Flow, e.g. `jina.ai`\n',
    prompt_type='input',
    depends_on=ADDITIONAL_USERS,
    conditional_check=lambda user_inp: user_inp.additional_user,
    post_func=lambda user_input, **kwargs: _add_additional_users(user_input, **kwargs),
)


def _set_value_to_none(user_input: UserInput):
    if not user_input.api_key:
        user_input.api_key = None


def _add_additional_users(user_input: UserInput, **kwargs):
    if not kwargs.get('user_emails', None):
        raise RetryException('Please provide at least one email address')
    user_input.user_emails = (
        [email.strip() for email in kwargs['user_emails'].split(',')]
        if kwargs['user_emails']
        else []
    )


def construct_app(app_name: str):
    return getattr(
        importlib.import_module(f'now.app.{app_name}.app'),
        f'{to_camel_case(app_name)}',
    )()


def _jina_auth_login(user_input: UserInput, **kwargs):
    try:
        jina_auth_login()
    except AuthenticationRequiredError:
        with yaspin_extended(
            sigmap=sigmap, text='Log in to Jina AI Cloud', color='green'
        ) as spinner:
            cmd('jina auth login')
        spinner.ok('🛠️')

    get_info_hubble(user_input)
    os.environ['JCLOUD_NO_SURVEY'] = '1'


app_config = [APP_NAME]
data_type = [DATASET_TYPE]
data_fields = [INDEX_FIELDS, FILTER_FIELDS]
data_demo = [DEMO_DATA]
data_da = [DOCARRAY_NAME, DATASET_PATH]
data_s3 = [DATASET_PATH_S3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME]
data_es = [
    ES_HOST_NAME,
    ES_INDEX_NAME,
    ES_ADDITIONAL_ARGS,
]
remote_cluster = [SECURED, API_KEY, ADDITIONAL_USERS, USER_EMAILS]

base_options = (
    data_type
    + data_demo
    + data_da
    + data_s3
    + data_es
    + data_fields
    + app_config
    + remote_cluster
)
