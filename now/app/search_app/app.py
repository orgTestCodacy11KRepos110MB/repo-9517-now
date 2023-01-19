import os
from typing import Dict, List, Tuple, TypeVar

from docarray.typing import Image, Text, Video
from jina import Client

from now.app.base.app import JinaNOWApp
from now.app.search_app.indexer_utils import check_if_ocr_needed
from now.constants import (
    ACCESS_PATHS,
    EXECUTOR_PREFIX,
    EXTERNAL_CLIP_HOST,
    NOW_AUTOCOMPLETE_VERSION,
    NOW_ELASTIC_INDEXER_VERSION,
    NOW_PREPROCESSOR_VERSION,
    Apps,
)
from now.demo_data import (
    AVAILABLE_DATASETS,
    DEFAULT_EXAMPLE_HOSTED,
    DemoDataset,
    DemoDatasetNames,
)
from now.executor.name_to_id_map import name_to_id_map
from now.now_dataclasses import UserInput
from now.utils import get_email


class SearchApp(JinaNOWApp):
    def __init__(self):
        super().__init__()

    @property
    def app_name(self) -> str:
        return Apps.SEARCH_APP

    @property
    def is_enabled(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return 'Search app'

    @property
    def required_docker_memory_in_gb(self) -> int:
        return 8

    @property
    def demo_datasets(self) -> Dict[TypeVar, List[DemoDataset]]:
        return AVAILABLE_DATASETS

    @property
    def finetune_datasets(self) -> [Tuple]:
        return DemoDatasetNames.DEEP_FASHION, DemoDatasetNames.BIRD_SPECIES

    def is_demo_available(self, user_input) -> bool:
        if (
            DEFAULT_EXAMPLE_HOSTED
            and user_input.dataset_name in DEFAULT_EXAMPLE_HOSTED
            and 'NOW_EXAMPLES' not in os.environ
            and 'NOW_CI_RUN' not in os.environ
        ):
            client = Client(
                host=f'grpcs://now-example-{self.app_name}-{user_input.dataset_name}.dev.jina.ai'.replace(
                    '_', '-'
                )
            )
            try:
                client.post('/dry_run', timeout=2)
            except Exception:
                return False
            return True
        return False

    @staticmethod
    def autocomplete_stub() -> Dict:
        return {
            'name': 'autocomplete_executor',
            'uses': f'{EXECUTOR_PREFIX}{name_to_id_map.get("NOWAutoCompleteExecutor2")}/{NOW_AUTOCOMPLETE_VERSION}',
            'needs': 'gateway',
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
        }

    @staticmethod
    def preprocessor_stub(use_high_perf_flow: bool) -> Dict:
        return {
            'name': 'preprocessor',
            'needs': 'autocomplete_executor',
            'replicas': 15 if use_high_perf_flow else 1,
            'uses': f'{EXECUTOR_PREFIX}{name_to_id_map.get("NOWPreprocessor")}/{NOW_PREPROCESSOR_VERSION}',
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
            'jcloud': {
                'resources': {
                    'memory': '1G',
                    'cpu': '0.5',
                    'capacity': 'on-demand',
                }
            },
        }

    @staticmethod
    def clip_encoder_stub() -> Tuple[Dict, int]:
        return {
            'name': 'encoderclip',
            'uses': f'{EXECUTOR_PREFIX}CLIPOnnxEncoder/0.8.1-gpu',
            'host': EXTERNAL_CLIP_HOST,
            'port': 443,
            'tls': True,
            'external': True,
            'uses_with': {'access_paths': ACCESS_PATHS, 'name': 'ViT-B-32::openai'},
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
            'needs': 'preprocessor',
        }, 512

    @staticmethod
    def sbert_encoder_stub() -> Tuple[Dict, int]:
        return {
            'name': 'encodersbert',
            'uses': f'{EXECUTOR_PREFIX}TransformerSentenceEncoder',
            'uses_with': {
                'access_paths': ACCESS_PATHS,
                'model_name': 'msmarco-distilbert-base-v3',
            },
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
            'needs': 'preprocessor',
        }, 768

    @staticmethod
    def indexer_stub(user_input: UserInput, encoder2dim: Dict[str, int]) -> Dict:
        """Creates indexer stub.

        :param user_input: User input
        :param encoder2dim: maps encoder name to its output dimension
        """
        if len(encoder2dim) != 1:
            raise ValueError(
                f'Indexer can only be created for one encoder but have encoders: {encoder2dim}'
            )
        else:
            encoder_name = list(encoder2dim.keys())[0]
            dim = encoder2dim[encoder_name]
        return {
            'name': 'indexer',
            'needs': encoder_name,
            'uses': f'{EXECUTOR_PREFIX}{name_to_id_map.get("NOWElasticIndexer")}/{NOW_ELASTIC_INDEXER_VERSION}',
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
            'uses_with': {
                'dim': dim,
                'ocr_is_needed': check_if_ocr_needed(user_input),
                'document_mappings': [
                    [
                        encoder_name,
                        dim,
                        list(user_input.field_names_to_dataclass_fields.values()),
                    ]
                ],
            },
            'jcloud': {
                'resources': {
                    'memory': '8G',
                    'cpu': 0.5,
                    'capacity': 'on-demand',
                }
            },
        }

    def get_executor_stubs(self, dataset, user_input: UserInput) -> Dict:
        """Returns a dictionary of executors to be added in the flow

        :param dataset: DocumentArray of the dataset
        :param user_input: user input
        :return: executors stubs with filled-in env vars
        """
        flow_yaml_executors = [
            self.autocomplete_stub(),
            self.preprocessor_stub(
                use_high_perf_flow=get_email().split('@')[-1] == 'jina.ai'
                and not any(
                    _var in os.environ for _var in ['NOW_CI_RUN', 'NOW_TESTING']
                )
            ),
        ]

        encoder2dim = {}
        # todo: comment out the following if-block to enable sbert for text index fields
        # if any(
        #     user_input.index_field_candidates_to_modalities[field] == Text
        #     for field in user_input.index_fields
        # ):
        #     sbert_encoder, sbert_dim = self.sbert_encoder_stub()
        #     encoder2dim[sbert_encoder['name']] = sbert_dim
        #     flow_yaml_executors.append(sbert_encoder)
        if any(
            user_input.index_field_candidates_to_modalities[field]
            in [Image, Video, Text]
            for field in user_input.index_fields
        ):
            clip_encoder, clip_dim = self.clip_encoder_stub()
            encoder2dim[clip_encoder['name']] = clip_dim
            flow_yaml_executors.append(clip_encoder)

        flow_yaml_executors.append(
            self.indexer_stub(user_input, encoder2dim=encoder2dim)
        )

        return flow_yaml_executors

    @property
    def max_request_size(self) -> int:
        """Max number of documents in one request"""
        return 10
