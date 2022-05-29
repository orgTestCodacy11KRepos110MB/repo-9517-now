from typing import Dict

import cowsay
from docarray import DocumentArray

from now.apps.base.app import JinaNOWApp
from now.constants import Modalities
from now.deployment.deployment import which
from now.run_backend import finetune_flow_setup


class music_to_music(JinaNOWApp):
    @property
    def description(self) -> str:
        return 'Music to music search'

    @property
    def input_modality(self) -> str:
        return Modalities.MUSIC

    @property
    def output_modality(self) -> str:
        return Modalities.MUSIC

    def check_requirements(self) -> bool:
        if not ffmpeg_is_installed():
            _handle_ffmpeg_install_required()
            return False
        return True

    def setup(self, da: DocumentArray, user_config: Dict, kubectl_path) -> Dict:
        return finetune_flow_setup(self, da, user_config, kubectl_path)


def ffmpeg_is_installed():
    return which("ffmpeg")


def _handle_ffmpeg_install_required():
    bc_red = '\033[91m'
    bc_end = '\033[0m'
    print()
    print(
        f"{bc_red}To use the audio modality you need the ffmpeg audio processing"
        f" library installed on your system.{bc_end}"
    )
    print(
        f"{bc_red}For MacOS please run 'brew install ffmpeg' and on"
        f" Linux 'apt-get install ffmpeg libavcodec-extra'.{bc_end}"
    )
    print(
        f"{bc_red}After the installation, restart Jina Now and have fun with music search 🎸!{bc_end}"
    )
    cowsay.cow('see you soon 👋')
    exit(1)
