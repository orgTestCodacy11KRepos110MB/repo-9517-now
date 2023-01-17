import os
from copy import deepcopy
from typing import Dict, List, Optional, Tuple, TypeVar

import docker
from docarray import DocumentArray
from jina import __version__ as jina_version
from jina.jaml import JAML

from now.app.base.preprocess import preprocess_image, preprocess_text, preprocess_video
from now.constants import DEFAULT_FLOW_NAME, NOW_GATEWAY_VERSION, PREFETCH_NR
from now.demo_data import DEFAULT_EXAMPLE_HOSTED, DemoDataset
from now.now_dataclasses import DialogOptions, UserInput


class JinaNOWApp:
    """
    Interface for Jina NOW applications.
    To create a new application, you need to inherit from this class and override the methods.
    Example:
        class TextToImageApp(JinaNowApp):
            pass
    """

    def __init__(self):
        flow_dir = os.path.abspath(os.path.join(__file__, '..'))
        self.flow_yaml = os.path.join(flow_dir, 'flow.yml')

    @property
    def app_name(self) -> str:
        """
        Name of the app. Should be an enum value set in now.constants.Apps
        """
        raise NotImplementedError()

    @property
    def is_enabled(self) -> bool:
        """
        Set to True if this app is enabled for the end user.
        """
        raise NotImplementedError()

    @property
    def description(self) -> str:
        """
        Short description of the app.
        """
        return 'Jina NOW app'

    @property
    def bff(self) -> Optional[str]:
        """
        TODO This function is currently not used but already introduces the concept of custom bff
        Used to configure the bff which is used to define input and output format.
        :return: the path to the file where the bff routs are configured
        """
        return None

    @property
    def playground(self) -> Optional[str]:
        """
        TODO This function is currently not used but already introduces the concept of custom playground
        Used to configure the playground(streamlit app) where the user can run example queries
        :return: the path to the streamlit file.
        """
        return None

    @property
    def options(self) -> List[DialogOptions]:
        """
        Get the options which are used to configure the app. Base class should override this function and
        return the list of their option. Check ``DialogOptions`` for the format of the options
        On CLI the user will get a prompt and at the storefront, a GUI will be generated accordingly.
        Example:
        ``return [options.your_custom_options`]``
        :return: List[DialogOptions]
        """
        return []

    @property
    def demo_datasets(self) -> Dict[TypeVar, List[DemoDataset]]:
        """Get a list of example datasets for the app."""
        raise NotImplementedError()

    @property
    def required_docker_memory_in_gb(self) -> int:
        """
        Recommended memory limit for the docker client to run this app.
        """
        return 8

    @property
    def finetune_datasets(self) -> [Tuple]:
        """Defines the list of demo datasets which are fine-tunable."""
        return ()

    def _check_docker_mem_limit(self) -> bool:
        mem_total = docker.from_env().info().get('MemTotal')
        if (
            mem_total is not None
            and mem_total / 1e9 < self.required_docker_memory_in_gb
        ):
            print(
                '🚨 Your docker container memory limit is set to ~{:.2f}GB'.format(
                    mem_total / 1e9
                )
                + f' which is below the recommended limit of {self.required_docker_memory_in_gb}GB'
                f' for the {self.app_name} app'
            )
            return False
        else:
            return True

    def set_app_parser(self, parser, formatter) -> None:
        """
        This parser reads from the `options` property and parses it
        to form the command line arguments for app
        """
        if self.is_enabled:
            parser = parser.add_parser(
                self.app_name,
                help=self.description,
                description=f'Create an {self.app_name} app.',
                formatter_class=formatter,
            )
            for option in self.options:
                if option.is_terminal_command:
                    parser.add_argument(
                        f'--{option.name}',
                        help=option.description,
                        type=str,
                    )

    def _check_requirements(self) -> bool:
        """
        Returns true if all requirements on the system are satisfied. Else False.
        """
        return True

    def run_checks(self, user_input: UserInput) -> bool:
        req_check = self._check_requirements()
        mem_check = True
        if user_input.deployment_type != 'remote':
            mem_check = self._check_docker_mem_limit()
        return req_check and mem_check

    def get_executor_stubs(self, dataset, user_input, **kwargs) -> Dict:
        """
        Returns the stubs for the executors in the flow.
        """
        raise NotImplementedError()

    def setup(self, dataset: DocumentArray, user_input: UserInput, **kwargs) -> Dict:
        """
        Runs before the flow is deployed.
        Common use cases:
            - create a database
            - finetune a model + push the artifact
            - notify other services
            - check if starting the app is currently possible
        :param dataset:
        :param user_input: user configuration based on the given options
        :return: dict used to replace variables in flow yaml and to clean up resources after the flow is terminated
        """
        # Get the common env variables
        common_env_dict = {
            'JINA_VERSION': jina_version,
            'PREFETCH': PREFETCH_NR,
            'ADMIN_EMAILS': user_input.admin_emails or [] if user_input.secured else [],
            'USER_EMAILS': user_input.user_emails or [] if user_input.secured else [],
            'API_KEY': [user_input.api_key]
            if user_input.secured and user_input.api_key
            else [],
            'CUSTOM_DNS': '',
        }
        if 'NOW_EXAMPLES' in os.environ:
            valid_app = DEFAULT_EXAMPLE_HOSTED.get(user_input.app_instance.app_name, {})
            is_demo_ds = user_input.dataset_name in valid_app
            if is_demo_ds:
                common_env_dict[
                    'CUSTOM_DNS'
                ] = f'now-example-{user_input.app_instance.app_name}-{user_input.dataset_name}.dev.jina.ai'.replace(
                    '_', '-'
                )
        # Read the flow and add generic configuration such as labels in the flow
        # Keep this function as simple as possible. It should only be used to add generic configuration needed
        # for all apps. App specific configuration should be added in the app specific setup function.
        with open(self.flow_yaml) as input_f:
            flow_yaml_content = JAML.load(input_f.read())
            flow_yaml_content['jcloud']['labels'] = {'team': 'now'}
            flow_yaml_content['jcloud']['name'] = (
                user_input.flow_name + '-' + DEFAULT_FLOW_NAME
                if user_input.flow_name != ''
                and user_input.flow_name != DEFAULT_FLOW_NAME
                else DEFAULT_FLOW_NAME
            )
            # update gateway version
            flow_yaml_content['gateway'][
                'uses'
            ] = f'jinahub+docker://2m00g87k/{NOW_GATEWAY_VERSION}'
            # Call the executor stubs function to get the executors for the flow
            flow_yaml_content['executors'] = self.get_executor_stubs(
                dataset, user_input
            )
            # append user_input and api_keys to all executors except the remote executors
            user_input_dict = deepcopy(user_input.__dict__)
            user_input_dict.pop('app_instance', None)
            user_input_dict.pop('index_field_candidates_to_modalities', None)
            for executor in flow_yaml_content['executors']:
                if not executor.get('external', False):
                    if not executor.get('uses_with', None):
                        executor['uses_with'] = {}
                    executor['uses_with']['user_input_dict'] = user_input_dict
                    if user_input.deployment_type == 'remote':
                        executor['uses_with']['api_keys'] = '${{ ENV.API_KEY }}'
                        executor['uses_with']['user_emails'] = '${{ ENV.USER_EMAILS }}'
                        executor['uses_with'][
                            'admin_emails'
                        ] = '${{ ENV.ADMIN_EMAILS }}'
            self.flow_yaml = self.add_telemetry_env(flow_yaml_content)

        return common_env_dict

    def preprocess(
        self,
        docs: DocumentArray,
    ) -> DocumentArray:
        """Loads and preprocesses every document such that it is ready for indexing."""
        for doc in docs:
            for chunk in doc.chunks:
                try:
                    if chunk.modality == 'text':
                        preprocess_text(chunk)
                    elif chunk.modality == 'image':
                        preprocess_image(chunk)
                    elif chunk.modality == 'video':
                        preprocess_video(chunk)
                    else:
                        raise ValueError(f'Unsupported modality {chunk.modality}')
                except Exception as e:
                    chunk.summary()
                    print(e)
        return docs

    def is_demo_available(self, user_input) -> bool:
        raise NotImplementedError()

    @property
    def max_request_size(self) -> int:
        """Max number of documents in one request"""
        return 32

    @staticmethod
    def add_telemetry_env(flow_yaml_content):
        if 'JINA_OPTOUT_TELEMETRY' in os.environ:
            flow_yaml_content['with']['env']['JINA_OPTOUT_TELEMETRY'] = os.environ[
                'JINA_OPTOUT_TELEMETRY'
            ]
            for executor in flow_yaml_content['executors']:
                executor['env']['JINA_OPTOUT_TELEMETRY'] = os.environ[
                    'JINA_OPTOUT_TELEMETRY'
                ]
        return flow_yaml_content
