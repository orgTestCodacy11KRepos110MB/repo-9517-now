import os
from typing import Dict

from docarray import DocumentArray

from now.app.base.app import JinaNOWApp
from now.common.preprocess import preprocess_images, preprocess_text
from now.common.utils import _get_clip_apps_with_dict, common_setup, get_indexer_config
from now.constants import CLIP_USES, Apps, DatasetTypes, Modalities
from now.now_dataclasses import UserInput


class ImageTextRetrieval(JinaNOWApp):
    def __init__(self):
        super().__init__()

    @property
    def app_name(self) -> str:
        return Apps.IMAGE_TEXT_RETRIEVAL

    @property
    def is_enabled(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return 'Image-text search app'

    @property
    def input_modality(self) -> Modalities:
        return Modalities.IMAGE_TEXT

    @property
    def output_modality(self) -> Modalities:
        return Modalities.IMAGE_TEXT

    @property
    def required_docker_memory_in_gb(self) -> int:
        return 8

    def set_flow_yaml(self, **kwargs):
        finetuning = kwargs.get('finetuning', False)

        now_package_dir = os.path.abspath(
            os.path.join(__file__, '..', '..', '..', '..')
        )
        flow_dir = os.path.join(now_package_dir, 'now', 'common', 'flow')

        if finetuning:
            self.flow_yaml = os.path.join(flow_dir, 'ft-flow-clip.yml')
        else:
            self.flow_yaml = os.path.join(flow_dir, 'flow-clip.yml')

    def setup(
        self, dataset: DocumentArray, user_input: UserInput, kubectl_path
    ) -> Dict:
        indexer_config = get_indexer_config(len(dataset))
        encoder_with, ocr_with = _get_clip_apps_with_dict(user_input)
        env_dict = common_setup(
            app_instance=self,
            user_input=user_input,
            dataset=dataset,
            encoder_uses=CLIP_USES[user_input.deployment_type][0],
            encoder_with=encoder_with,
            encoder_uses_with={
                'pretrained_model_name_or_path': CLIP_USES[user_input.deployment_type][
                    1
                ]
            },
            pre_trained_embedding_size=CLIP_USES[user_input.deployment_type][2],
            indexer_uses=indexer_config['indexer_uses'],
            kubectl_path=kubectl_path,
            indexer_resources=indexer_config['indexer_resources'],
        )
        env_dict.update(ocr_with)
        super().setup(dataset=dataset, user_input=user_input, kubectl_path=kubectl_path)
        return env_dict

    def preprocess(
        self, da: DocumentArray, user_input: UserInput, is_indexing=False
    ) -> DocumentArray:
        if is_indexing:
            if user_input.output_modality == Modalities.TEXT:
                split_by_sentences = False
                if (
                    user_input
                    and user_input.dataset_type == DatasetTypes.PATH
                    and user_input.dataset_path
                    and os.path.isdir(user_input.dataset_path)
                ):
                    # for text loaded from folder can't assume it is split by sentences
                    split_by_sentences = True
                return preprocess_text(da=da, split_by_sentences=split_by_sentences)
            else:
                return preprocess_images(da=da)
        return preprocess_images(da=da) + preprocess_text(da=da)
