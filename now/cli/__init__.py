import os
import pathlib
import platform
import sys
import warnings
from argparse import Namespace
from os.path import expanduser as user

import cpuinfo

from now import __version__
from now import __version__ as version
from now.constants import SURVEY_LINK
from now.deployment.deployment import cmd
from now.run_all_k8s import start_now, stop_now
from now.system_information import get_system_state

warnings.filterwarnings("ignore")

cur_dir = pathlib.Path(__file__).parents[1].resolve()

os.environ['JINA_CHECK_VERSION'] = 'False'
os.environ['JCLOUD_LOGLEVEL'] = 'ERROR'


def _get_run_args():
    from now.cli.parser import get_main_parser

    parser = get_main_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        exit()
    args, unknown = parser.parse_known_args()

    # clean up the args with None values
    args = {k: v for k, v in vars(args).items() if v is not None}
    # Convert args back to Namespace
    args = Namespace(**args)

    if unknown:
        raise Exception('unknown args: ', unknown)

    return args


def _is_latest_version(suppress_on_error=True):
    try:
        import json
        from urllib.request import Request, urlopen

        from jina import __version__

        req = Request(
            'https://api.jina.ai/latest', headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urlopen(
            req, timeout=5
        ) as resp:  # 'with' is important to close the resource after use
            latest_ver = json.load(resp)['version']
            from packaging.version import Version

            latest_ver = Version(latest_ver)
            cur_ver = Version(__version__)
            if cur_ver < latest_ver:
                from jina.logging.predefined import default_logger

                default_logger.warning(
                    f'You are using Jina version {cur_ver}, however version {latest_ver} is available. '
                    f'You should consider upgrading via the "pip install --upgrade jina" command.'
                )
                return False
        return True
    except Exception:
        if not suppress_on_error:
            raise


def get_task(kwargs):
    for x in ['cli', 'now']:
        if x in kwargs:
            return kwargs[x]
    raise Exception('kwargs do not contain a task')


def cli(args=None):
    """The main entrypoint of the CLI"""
    os.environ['JINA_LOG_LEVEL'] = 'CRITICAL'
    print_version_line()
    kwargs = parse_args(args)
    task = get_task(kwargs)
    if '--version' in sys.argv[1:]:
        print(__version__)
        exit(0)
    if task == 'start':
        return start_now(
            **kwargs,
        )
    elif task == 'stop':
        return stop_now(**kwargs)
    elif task == 'survey':
        import webbrowser

        webbrowser.open(SURVEY_LINK, new=0, autoraise=True)
    else:
        raise Exception(f'unknown task, {task}')


def parse_args(args):
    if not args:
        args = _get_run_args()
    args = vars(args)  # Make it a dict from Namespace
    return args


def print_version_line():
    if len(sys.argv) != 1 and not ('-h' in sys.argv[1:] or '--help' in sys.argv[1:]):
        print(f'Initialising Jina NOW v{version} ...')


if __name__ == '__main__':
    cli()
