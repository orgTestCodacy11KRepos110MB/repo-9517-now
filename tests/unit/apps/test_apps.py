import os

import pytest
from docarray import Document, DocumentArray
from docarray.typing import Text

from now.app.search_app import SearchApp
from now.app.search_app.app import SearchApp
from now.common.options import construct_app
from now.constants import Apps
from now.now_dataclasses import UserInput


def test_app_attributes():
    """Test if all essential app attributes are defined"""
    for app in Apps():
        app_instance = construct_app(app)
        if app_instance.is_enabled:
            assert app_instance.app_name
            assert app_instance.description


def test_split_text_preprocessing():
    """Test if splitting of sentences is carried out when preprocessing text documents at indexing time"""
    app = SearchApp()
    da = DocumentArray(
        [Document(chunks=[Document(text='test. test', modality='text')])]
    )
    new_da = app.preprocess(da)
    assert len(new_da) == 1
    assert len(new_da[0].chunks) == 1
    assert len(new_da[0].chunks[0].chunks) == 2


@pytest.mark.parametrize('disable', [False, True])
def test_disable_telemetry(disable):
    initial_value = os.environ.get('JINA_OPTOUT_TELEMETRY')
    if disable:
        os.environ['JINA_OPTOUT_TELEMETRY'] = 'disableTelemetry'
    else:
        os.environ.pop('JINA_OPTOUT_TELEMETRY', None)

    expected_value = 'disableTelemetry' if disable else None

    app = SearchApp()
    user_input = UserInput()
    user_input.flow_name = 'flow'
    user_input.index_field_candidates_to_modalities = {'text': Text}
    user_input.index_fields = ['text']
    user_input.deployment_type = 'local'
    user_input.app_instance = app
    da = DocumentArray(
        [Document(chunks=[Document(text='test. test', modality='text')])]
    )

    app.setup(
        dataset=da, user_input=user_input, kubectl_path='kube_path', data_class=None
    )

    assert (
        app.flow_yaml['gateway']['env'].get('JINA_OPTOUT_TELEMETRY') == expected_value
    )
    for executor in app.flow_yaml['executors']:
        assert executor['env'].get('JINA_OPTOUT_TELEMETRY') == expected_value

    if initial_value:
        os.environ['JINA_OPTOUT_TELEMETRY'] = initial_value
