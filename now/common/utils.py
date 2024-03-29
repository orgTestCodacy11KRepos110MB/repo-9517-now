import json
import os
import pathlib
import tempfile
import time
from copy import deepcopy
from os.path import expanduser as user
from typing import Dict, List, Optional, Tuple

import hubble
from docarray import Document, DocumentArray
from jina import __version__ as jina_version
from jina.helper import random_port

from now.app.base.app import JinaNOWApp
from now.constants import (
    EXECUTOR_PREFIX,
    EXTERNAL_CLIP_HOST,
    NOW_AUTOCOMPLETE_VERSION,
    NOW_ELASTIC_INDEXER_VERSION,
    NOW_PREPROCESSOR_VERSION,
    NOW_QDRANT_INDEXER_VERSION,
    PREFETCH_NR,
    TAG_INDEXER_DOC_HAS_TEXT,
    DatasetTypes,
    Modalities,
)
from now.demo_data import DEFAULT_EXAMPLE_HOSTED
from now.deployment.deployment import cmd
from now.executor.name_to_id_map import name_to_id_map
from now.finetuning.run_finetuning import finetune
from now.finetuning.settings import FinetuneSettings, parse_finetune_settings
from now.now_dataclasses import UserInput
from now.utils import maybe_download_from_s3

cur_dir = pathlib.Path(__file__).parent.resolve()


MAX_RETRIES = 20


def common_get_flow_env_dict(
    finetune_settings: FinetuneSettings,
    encoder_uses: str,
    encoder_with: Dict,
    encoder_uses_with: Dict,
    pre_trained_embedding_size: int,
    indexer_uses: str,
    indexer_resources: Dict,
    user_input: UserInput,
    tags: List,
):
    """Returns dictionary for the environments variables for the clip & music flow.yml files."""
    if (
        finetune_settings.perform_finetuning and finetune_settings.bi_modal
    ) or user_input.app_instance.app_name == 'music_to_music':
        pre_trained_embedding_size = pre_trained_embedding_size * 2

    config = {
        'JINA_VERSION': jina_version,
        'ENCODER_NAME': f'{EXECUTOR_PREFIX}{encoder_uses}',
        'CAST_CONVERT_NAME': f'{EXECUTOR_PREFIX}CastNMoveNowExecutor/v0.0.3',
        'N_DIM': finetune_settings.finetune_layer_size
        if finetune_settings.perform_finetuning
        or user_input.app_instance.app_name == 'music_to_music'
        else pre_trained_embedding_size,
        'PRE_TRAINED_EMBEDDINGS_SIZE': pre_trained_embedding_size,
        'INDEXER_NAME': f'{EXECUTOR_PREFIX}{indexer_uses}',
        'PREFETCH': PREFETCH_NR,
        'PREPROCESSOR_NAME': f'{EXECUTOR_PREFIX}{name_to_id_map.get("NOWPreprocessor")}/{NOW_PREPROCESSOR_VERSION}',
        'AUTOCOMPLETE_EXECUTOR_NAME': f'{EXECUTOR_PREFIX}{name_to_id_map.get("NOWAutoCompleteExecutor2")}/{NOW_AUTOCOMPLETE_VERSION}',
        'APP': user_input.app_instance.app_name,
        'COLUMNS': tags,
        'ADMIN_EMAILS': user_input.admin_emails or [] if user_input.secured else [],
        'USER_EMAILS': user_input.user_emails or [] if user_input.secured else [],
        'API_KEY': [user_input.api_key]
        if user_input.secured and user_input.api_key
        else [],
        **encoder_with,
        **indexer_resources,
    }

    if encoder_uses_with.get('pretrained_model_name_or_path'):
        config['PRE_TRAINED_MODEL_NAME'] = encoder_uses_with[
            "pretrained_model_name_or_path"
        ]
    if finetune_settings.perform_finetuning:
        config['FINETUNE_ARTIFACT'] = finetune_settings.finetuned_model_artifact
        config['JINA_TOKEN'] = finetune_settings.token

    config['CUSTOM_DNS'] = ''
    if 'NOW_EXAMPLES' in os.environ:
        valid_app = DEFAULT_EXAMPLE_HOSTED.get(user_input.app_instance.app_name, {})
        is_demo_ds = user_input.dataset_name in valid_app
        if is_demo_ds:
            config[
                'CUSTOM_DNS'
            ] = f'now-example-{user_input.app_instance.app_name}-{user_input.dataset_name}.dev.jina.ai'
            config['CUSTOM_DNS'] = config['CUSTOM_DNS'].replace('_', '-')

    return config


def common_setup(
    app_instance: JinaNOWApp,
    user_input: UserInput,
    dataset: DocumentArray,
    encoder_uses: str,
    encoder_uses_with: Dict,
    indexer_uses: str,
    pre_trained_embedding_size: int,
    kubectl_path: str,
    encoder_with: Optional[Dict] = {},
    indexer_resources: Optional[Dict] = {},
) -> Dict:
    # should receive pre embedding size
    finetune_settings = parse_finetune_settings(
        pre_trained_embedding_size=pre_trained_embedding_size,
        user_input=user_input,
        dataset=dataset,
        finetune_datasets=app_instance.finetune_datasets,
        model_name='mlp',
        add_embeddings=True,
        loss='TripletMarginLoss',
    )
    tags = _extract_tags_for_indexer(deepcopy(dataset[0]), user_input)
    env_dict = common_get_flow_env_dict(
        finetune_settings=finetune_settings,
        encoder_uses=encoder_uses,
        encoder_with=encoder_with,
        encoder_uses_with=encoder_uses_with,
        pre_trained_embedding_size=pre_trained_embedding_size,
        indexer_uses=indexer_uses,
        indexer_resources=indexer_resources,
        user_input=user_input,
        tags=tags,
    )

    if finetune_settings.perform_finetuning:
        try:
            artifact_id, token = finetune(
                finetune_settings=finetune_settings,
                app_instance=app_instance,
                dataset=dataset,
                user_input=user_input,
                env_dict=env_dict,
                kubectl_path=kubectl_path,
            )

            finetune_settings.finetuned_model_artifact = artifact_id
            finetune_settings.token = token

            env_dict['FINETUNE_ARTIFACT'] = finetune_settings.finetuned_model_artifact
            env_dict['JINA_TOKEN'] = finetune_settings.token
        except Exception as e:
            print(
                'Finetuning is currently offline. The program execution still continues without'
                ' finetuning. Please report the following exception to us:'
            )
            import traceback

            traceback.print_exc()
            finetune_settings.perform_finetuning = False

    app_instance.set_flow_yaml(
        finetuning=finetune_settings.perform_finetuning, dataset_len=len(dataset)
    )
    return env_dict


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


def get_indexer_config(
    num_indexed_samples: int,
    elastic: Optional[bool] = False,
    kubectl_path: str = None,
    deployment_type: str = None,
) -> Dict:
    """Depending on the number of samples, which will be indexed, indexer and its resources are determined.

    :param num_indexed_samples: number of samples which will be indexed; should incl. chunks for e.g. text-to-video app
    :param elastic: hack to use NOWElasticIndexer, should be changed in future.
    :param kubectl_path: path to kubectl binary
    :param deployment_type: deployment type, e.g. 'remote' or 'local'
    :return: dict with indexer and its resource config
    """

    if elastic and deployment_type == 'local':
        config = {
            'indexer_uses': f'{name_to_id_map.get("NOWElasticIndexer")}/{NOW_ELASTIC_INDEXER_VERSION}',
            'hosts': setup_elastic_service(kubectl_path),
        }
    elif elastic and deployment_type == 'remote':
        raise ValueError(
            'NOWElasticIndexer is currently not supported for remote deployment. Please use local deployment.'
        )
    else:
        config = {
            'indexer_uses': f'{name_to_id_map.get("NOWQdrantIndexer16")}/{NOW_QDRANT_INDEXER_VERSION}'
        }
    threshold1 = 250_000
    if num_indexed_samples <= threshold1:
        config['indexer_resources'] = {'INDEXER_CPU': 0.1, 'INDEXER_MEM': '2G'}
    else:
        config['indexer_resources'] = {'INDEXER_CPU': 1.0, 'INDEXER_MEM': '4G'}

    return config


def _extract_tags_for_indexer(d: Document, user_input):
    with tempfile.TemporaryDirectory() as tmpdir:
        if user_input and user_input.dataset_type == DatasetTypes.S3_BUCKET:
            maybe_download_from_s3(
                docs=DocumentArray([d]),
                tmpdir=tmpdir,
                user_input=user_input,
                max_workers=1,
            )
    tags = set()
    for tag, _ in d.tags.items():
        tags.add((tag, str(tag.__class__.__name__)))
    final_tags = [list(tag) for tag in tags]
    if user_input.app_instance.output_modality in [
        Modalities.IMAGE,
        Modalities.VIDEO,
    ]:
        final_tags.append([TAG_INDEXER_DOC_HAS_TEXT, str(bool.__name__)])
    return final_tags


def setup_elastic_service(
    kubectl_path: str,
) -> str:
    """Setup ElasticSearch service and return a connection string to connect to the service with.

    :param kubectl_path: path to kubectl binary
    :return: connection string for connecting to the ElasticSearch service.
    """
    cur_dir = pathlib.Path(__file__).parent.resolve()
    cmd(
        f'{kubectl_path} create -f https://download.elastic.co/downloads/eck/2.4.0/crds.yaml'
    )
    cmd(
        f'{kubectl_path} apply -f https://download.elastic.co/downloads/eck/2.4.0/operator.yaml'
    )
    cmd(f'{kubectl_path} create ns nowapi')
    cmd(f'{kubectl_path} apply -f {cur_dir}/../deployment/elastic_kind.yml')
    num_retries = 0
    es_password, error_msg = '', b''
    while num_retries < MAX_RETRIES:
        es_password, error_msg = cmd(
            [
                kubectl_path,
                "get",
                "secret",
                "quickstart-es-elastic-user",
                "-o",
                "go-template='{{.data.elastic | base64decode}}'",
            ]
        )
        if es_password:
            es_password = es_password.decode("utf-8")[1:-1]
            break
        else:
            num_retries += 1
            time.sleep(2)
    if not es_password:
        raise Exception(error_msg.decode("utf-8"))
    host = f"https://elastic:{es_password}@quickstart-es-http.default:9200"
    return host


def _get_clip_apps_with_dict(user_input: UserInput) -> Tuple[Dict, Dict]:
    """Depending on whether this app will be remotely deployed, this function returns the with
    dictionary for the CLIP executor."""
    is_remote = user_input.deployment_type == 'remote'
    encoder_with = {
        'ENCODER_HOST': EXTERNAL_CLIP_HOST if is_remote else '0.0.0.0',
        'ENCODER_PORT': 443 if is_remote else random_port(),
        'IS_REMOTE_DEPLOYMENT': is_remote,
    }
    return encoder_with
