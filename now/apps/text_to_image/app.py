from typing import Dict, List

from docarray import DocumentArray
from now_common import options

from now.apps.base.app import JinaNOWApp
from now.constants import (
    CLIP_USES,
    IMAGE_MODEL_QUALITY_MAP,
    Apps,
    DemoDatasets,
    Modalities,
)
from now.dataclasses import UserInput
from now.run_backend import finetune_flow_setup


class TextToImage(JinaNOWApp):
    @property
    def description(self) -> str:
        return 'Text to image search'

    @property
    def input_modality(self) -> Modalities:
        return Modalities.TEXT

    @property
    def output_modality(self) -> Modalities:
        return Modalities.IMAGE

    @property
    def options(self) -> List[Dict]:
        return [options.QUALITY_CLIP]

    def set_app_parser(self, parser, formatter):
        parser = parser.add_parser(
            Apps.TEXT_TO_IMAGE,
            help='Text To Image App.',
            description='Create an `Text To Image` app.',
            formatter_class=formatter,
        )
        super().set_app_parser(parser, formatter)

    def setup(self, da: DocumentArray, user_config: UserInput, kubectl_path) -> Dict:
        return finetune_flow_setup(
            self,
            da,
            user_config,
            kubectl_path,
            encoder_uses=CLIP_USES,
            artifact=IMAGE_MODEL_QUALITY_MAP[user_config.quality][1],
            finetune_datasets=(DemoDatasets.DEEP_FASHION, DemoDatasets.BIRD_SPECIES),
        )
