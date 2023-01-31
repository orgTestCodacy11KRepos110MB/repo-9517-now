import os
from typing import Dict, List, Tuple, TypeVar

from jina import Client

from now.app.base.app import JinaNOWApp
from now.constants import (
    ACCESS_PATHS,
    DEMO_NS,
    EXTERNAL_CLIP_HOST,
    NOW_AUTOCOMPLETE_VERSION,
    NOW_ELASTIC_INDEXER_VERSION,
    NOW_PREPROCESSOR_VERSION,
    Apps,
    DatasetTypes,
    Models,
)
from now.demo_data import AVAILABLE_DATASETS, DemoDataset, DemoDatasetNames
from now.executor.name_to_id_map import name_to_id_map
from now.now_dataclasses import UserInput


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
            user_input.dataset_type == DatasetTypes.DEMO
            and 'NOW_EXAMPLES' not in os.environ
            and 'NOW_CI_RUN' not in os.environ
        ):
            client = Client(
                host=f'grpcs://{DEMO_NS.format(user_input.dataset_name.split("/")[-1])}.dev.jina.ai'
            )
            try:
                client.post('/dry_run', timeout=2)
            except Exception as e:  # noqa E722
                pass
            return True
        return False

    @staticmethod
    def autocomplete_stub() -> Dict:
        return {
            'name': 'autocomplete_executor',
            'uses': f'jinahub+docker://{name_to_id_map.get("NOWAutoCompleteExecutor2")}/{NOW_AUTOCOMPLETE_VERSION}',
            'needs': 'gateway',
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
        }

    @staticmethod
    def preprocessor_stub() -> Dict:
        return {
            'name': 'preprocessor',
            'needs': 'autocomplete_executor',
            'uses': f'jinahub+docker://{name_to_id_map.get("NOWPreprocessor")}/{NOW_PREPROCESSOR_VERSION}',
            'jcloud': {
                'autoscale': {'min': 0, 'max': 5, 'metric': 'concurrency', 'target': 1}
            },
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
        }

    @staticmethod
    def clip_encoder_stub() -> Tuple[Dict, int]:
        return {
            'name': Models.CLIP_MODEL,
            'uses': f'jinahub+docker://CLIPOnnxEncoder/0.8.1-gpu',
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
            'name': Models.SBERT_MODEL,
            'uses': f'jinahub+docker://TransformerSentenceEncoder',
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
        document_mappings_list = []

        for encoder, dim in encoder2dim.items():
            document_mappings_list.append(
                [
                    encoder,
                    dim,
                    [
                        user_input.field_names_to_dataclass_fields[
                            index_field.replace('_model', '')
                        ]
                        for index_field, encoders in user_input.model_choices.items()
                        if encoder in encoders
                    ],
                ]
            )

        return {
            'name': 'indexer',
            'needs': list(encoder2dim.keys()),
            'uses': f'jinahub+docker://{name_to_id_map.get("NOWElasticIndexer")}/{NOW_ELASTIC_INDEXER_VERSION}',
            'env': {'JINA_LOG_LEVEL': 'DEBUG'},
            'uses_with': {
                'document_mappings': document_mappings_list,
            },
            'no_reduce': True,
            'jcloud': {
                'resources': {
                    'memory': '8G',
                    'cpu': 0.5,
                    'capacity': 'on-demand',
                }
            },
        }

    def get_executor_stubs(self, dataset, user_input: UserInput) -> List[Dict]:
        """Returns a dictionary of executors to be added in the flow

        :param dataset: DocumentArray of the dataset
        :param user_input: user input
        :return: executors stubs with filled-in env vars
        """
        flow_yaml_executors = [
            self.autocomplete_stub(),
            self.preprocessor_stub(),
        ]

        encoder2dim = {}
        if any(
            Models.SBERT_MODEL in user_input.model_choices[f"{field}_model"]
            for field in user_input.index_fields
        ):
            sbert_encoder, sbert_dim = self.sbert_encoder_stub()
            encoder2dim[sbert_encoder['name']] = sbert_dim
            flow_yaml_executors.append(sbert_encoder)

        if any(
            Models.CLIP_MODEL in user_input.model_choices[f"{field}_model"]
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
