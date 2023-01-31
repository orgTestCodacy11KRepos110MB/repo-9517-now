from __future__ import annotations, print_function, unicode_literals

import base64
import json
import os
import shutil
import signal
import sys
import tempfile
from collections.abc import MutableMapping
from concurrent.futures import ThreadPoolExecutor
from os.path import expanduser as user
from typing import Dict, List, Optional, TypeVar, Union

import boto3
import docarray
import hubble
import yaml
from docarray import Document, DocumentArray
from jina.jaml import JAML
from pyfiglet import Figlet

from now.thirdparty.PyInquirer.prompt import prompt


def download_file(path, r_raw):
    with path.open("wb") as f:
        shutil.copyfileobj(r_raw, f)


def download(url, filename):
    import functools
    import pathlib

    import requests
    from tqdm.auto import tqdm

    r = requests.get(url, stream=True, allow_redirects=True)
    if r.status_code != 200:
        r.raise_for_status()  # Will only raise for 4xx codes, so...
        raise RuntimeError(f"Request to {url} returned status code {r.status_code}")
    file_size = int(r.headers.get('Content-Length', 0))

    path = pathlib.Path(filename).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    desc = "(Unknown total file size)" if file_size == 0 else ""
    r.raw.read = functools.partial(
        r.raw.read, decode_content=True
    )  # Decompress if needed

    if any(map(lambda x: x in os.environ, ['NOW_CI_RUN', 'NOW_EXAMPLES'])):
        download_file(path, r.raw)
    else:
        with tqdm.wrapattr(r.raw, "read", total=file_size, desc=desc) as r_raw:
            download_file(path, r_raw)

    return path


def my_handler(signum, frame, spinner):
    with spinner.hidden():
        sys.stdout.write("Program terminated!\n")
    spinner.stop()
    exit(0)


def flow_definition(dirpath) -> Dict:
    with open(dirpath) as f:
        return yaml.safe_load(f.read())


class BetterEnum:
    def __iter__(self):
        return [getattr(self, x) for x in dir(self) if ('__' not in x)].__iter__()


def to_camel_case(text):
    """Convert text to camel case in great coding style"""
    s = text.replace("_", " ")
    s = s.split()
    return ''.join(i.capitalize() for i in s)


sigmap = {signal.SIGINT: my_handler, signal.SIGTERM: my_handler}


class EnvironmentVariables:
    def __init__(self, envs: Dict):
        self._env_keys_added: Dict = envs

    def __enter__(self):
        for key, val in self._env_keys_added.items():
            os.environ[key] = str(val)

    def __exit__(self, *args, **kwargs):
        for key in self._env_keys_added.keys():
            os.unsetenv(key)


def add_env_variables_to_flow(app_instance, env_dict: Dict):
    with EnvironmentVariables(env_dict):
        app_instance.flow_yaml = JAML.expand_dict(app_instance.flow_yaml, env_dict)


def write_env_file(env_file, config):
    config_string = '\n'.join([f'{key}={value}' for key, value in config.items()])
    with open(env_file, 'w+') as fp:
        fp.write(config_string)


def write_flow_file(flow_yaml_content, new_yaml_file_path):
    with open(new_yaml_file_path, 'w') as f:
        JAML.dump(
            flow_yaml_content,
            f,
            indent=2,
            allow_unicode=True,
            Dumper=Dumper,
        )


@hubble.login_required
def jina_auth_login():
    pass


def get_info_hubble(user_input):
    client = hubble.Client(max_retries=None, jsonify=True)
    response = client.get_user_info()
    user_input.admin_emails = (
        [response['data']['email']] if 'email' in response['data'] else []
    )
    if not user_input.admin_emails:
        print(
            'Your hubble account is not verified. Please verify your account to deploy your flow as admin.'
        )
    user_input.jwt = {'token': client.token}
    user_input.admin_name = response['data']['name']
    return response['data'], client.token


def print_headline():
    f = Figlet(font='slant')
    print('Welcome to:')
    print(f.renderText('Jina NOW'))
    print('Get your search use case up and running - end to end.\n')
    print(
        'You can choose between image and text search. \nJina NOW trains a model, pushes it to Jina AI Cloud '
        'and deploys a Flow and playground app in the cloud or locally. \nCheck out our demos or bring '
        'your own data.\n'
    )
    print('Visit docs.jina.ai to learn more about our framework')
    print(
        '💡 Make sure you give enough memory to your Docker daemon. '
        '5GB - 8GB should be okay.'
    )
    print()


def maybe_prompt_user(questions, attribute, **kwargs):
    """
    Checks the `kwargs` for the `attribute` name. If present, the value is returned directly.
    If not, the user is prompted via the cmd-line using the `questions` argument.

    :param questions: A dictionary that is passed to `PyInquirer.prompt`
        See docs: https://github.com/CITGuru/PyInquirer#documentation
    :param attribute: Name of the value to get. Make sure this matches the name in `kwargs`

    :return: A single value of either from `kwargs` or the user cli input.
    """
    if kwargs and attribute in kwargs:
        return kwargs[attribute]
    else:
        answer = prompt(questions)
        return answer[attribute]


def prompt_value(
    name: str,
    prompt_message: str,
    prompt_type: str = 'input',
    choices: Optional[List[Union[Dict, str]]] = None,
    **kwargs: Dict,
):
    qs = {'name': name, 'type': prompt_type, 'message': prompt_message}

    if choices is not None:
        qs['choices'] = choices
    return maybe_prompt_user(qs, name, **kwargs)


def get_local_path(tmpdir, path_s3):
    # todo check if this method of creatign the path is creating too much overhead
    # also, the number of files is growing and will never be cleaned up
    return os.path.join(
        str(tmpdir),
        base64.b64encode(bytes(path_s3, "utf-8")).decode("utf-8")
        + f'.{path_s3.split(".")[-1] if "." in path_s3 else ""}',  # preserve file ending
    )


def download_from_bucket(tmpdir, uri, bucket):
    path_s3 = '/'.join(uri.split('/')[3:])
    path_local = get_local_path(tmpdir, path_s3)
    bucket.download_file(
        path_s3,
        path_local,
    )
    return path_local


def convert_fn(
    d: Document, tmpdir, aws_access_key_id, aws_secret_access_key, aws_region_name
) -> Document:
    """Downloads files and tags from S3 bucket and updates the content uri and the tags uri to the local path"""

    bucket = get_bucket(
        uri=d.uri,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region_name,
    )
    d.tags['uri'] = d.uri

    d.uri = download_from_bucket(tmpdir, d.uri, bucket)
    if d.uri.endswith('.json'):
        d.load_uri_to_text()
        json_dict = json.loads(d.text)
        field_name = d._metadata['field_name']
        field_value = get_dict_value_for_flattened_key(
            json_dict, field_name.split('__')
        )
        d.text = field_value
        d.uri = ''
    return d


def get_bucket(uri, aws_access_key_id, aws_secret_access_key, region_name):
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )
    bucket = session.resource('s3').Bucket(uri.split('/')[2])
    return bucket


def maybe_download_from_s3(
    docs: DocumentArray, tmpdir: tempfile.TemporaryDirectory, user_input, max_workers
):
    """Downloads file to local temporary dictionary, saves S3 URI to `tags['uri']` and modifies `uri` attribute of
    document to local path in-place.

    :param doc: document containing URI pointing to the location on S3 bucket
    :param tmpdir: temporary directory in which files will be saved
    :param user_input: User iput which contain aws credentials
    :param max_workers: number of threads to create in the threadpool executor to make execution faster
    """

    flat_docs = docs['@c']
    filtered_docs = [c for c in flat_docs if c.uri.startswith('s3://')]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for c in filtered_docs:
            f = executor.submit(
                convert_fn,
                c,
                tmpdir,
                user_input.aws_access_key_id,
                user_input.aws_secret_access_key,
                user_input.aws_region_name,
            )
            futures.append(f)
        for f in futures:
            f.result()


def flatten_dict(d, parent_key='', sep='__'):
    """
    This function converts a nested dictionary into a dictionary of attirbutes using '__' as a separator.
    Example:
        {'a': {'b': {'c': 1, 'd': 2}}} -> {'a__b__c': 1, 'a__b__c': 2}
    """
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            # TODO for now, we just have string values, str(v) should be removed once we support numeric values
            items.append((new_key, str(v)))
    return dict(items)


def get_dict_value_for_flattened_key(d, keys):
    if len(keys) == 0:
        return d
    else:
        return get_dict_value_for_flattened_key(d[keys[0]], keys[1:])


def _get_context_names(contexts, active_context=None):
    names = [c for c in contexts] if contexts is not None else []
    if active_context is not None:
        names.remove(active_context)
        names = [active_context] + names
    return names


def get_flow_id(host):
    return host.split('.wolf.jina.ai')[0].split('grpcs://')[-1]


class Dumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)


def get_email():
    try:
        with open(user('~/.jina/config.json')) as fp:
            config_val = json.load(fp)
            user_token = config_val['auth_token']
            client = hubble.Client(token=user_token, max_retries=None, jsonify=True)
            response = client.get_user_info()
        if 'email' in response['data']:
            return response['data']['email']
        return ''
    except FileNotFoundError:
        return ''


def docarray_typing_to_modality_string(T: TypeVar) -> str:
    """E.g. docarray.typing.Image -> image"""
    return T.__name__.lower()


def modality_string_to_docarray_typing(s: str) -> TypeVar:
    """E.g. image -> docarray.typing.Image"""
    return getattr(docarray.typing, s.capitalize())


# Add a custom retry exception
class RetryException(Exception):
    pass


class DemoAvailableException(Exception):
    pass
