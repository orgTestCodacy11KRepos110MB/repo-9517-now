import json

import pytest
from docarray import Document
from jina import Executor, Flow, requests

from now.executor.abstract.auth.auth import get_auth_executor_class
from now.executor.gateway import NOWGateway


@pytest.fixture
def auth_executor():
    return get_auth_executor_class()


def test_executor_persistence(auth_executor, tmpdir):
    api_key = 'my_key'
    e = auth_executor(api_keys=[api_key], metas={'workspace': tmpdir})
    e.update_user_emails(
        parameters={'api_key': api_key, 'user_emails': ['abc@test.ai']}
    )
    with open(e.user_emails_path, 'r') as fp:
        json.load(fp)
    e.update_api_keys(parameters={'api_key': api_key, 'api_keys': ['your_key']})
    with open(e.user_emails_path, 'r') as fp:
        json.load(fp)


class SecondExecutor(Executor):
    @requests
    def do_something(self, *args, **kwargs):
        print('do something')


def test_authorization_success_api_key(auth_executor, admin_email):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={
                'admin_emails': [admin_email],
                'api_keys': ['valid_key'],
            },
        )
        .add(uses=SecondExecutor)
    ) as f:
        f.index(inputs=Document(text='abc'), parameters={'api_key': 'valid_key'})


def test_authorization_failed(auth_executor, admin_email):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'admin_emails': [admin_email]},
        )
        .add(uses=SecondExecutor)
    ) as f:
        with pytest.raises(Exception):
            f.index(
                inputs=Document(text='abc'),
                parameters={'jwt': {'token': 'invalid token of abc.def@jina.ai'}},
            )


def test_authorization_successful(auth_executor, admin_email, mock_hubble_admin_email):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'admin_emails': [admin_email]},
        )
        .add(uses=SecondExecutor)
    ) as f:
        f.index(
            inputs=Document(text='abc'),
            parameters={
                'jwt': {
                    "token": 'yet:another:admin:token',
                }
            },
        )


def test_authorization_success_domain_users(
    auth_executor, mock_hubble_domain_user_email
):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'user_emails': ['test.ai']},
        )
        .add(uses=SecondExecutor)
    ) as f:
        f.index(
            inputs=Document(text='abc'),
            parameters={
                'jwt': {
                    "token": 'another:test:ai:user:token',
                }
            },
        )


def test_authorization_success_jina_users(auth_executor, mock_hubble_user_email):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'admin_emails': ['test.ai']},
        )
        .add(uses=SecondExecutor)
    ) as f:
        f.index(
            inputs=Document(text='abc'),
            parameters={
                'jwt': {
                    "token": 'another:jina:ai:user:token',
                }
            },
        )


def test_authorization_failed_domain_users(
    auth_executor, mock_hubble_domain_user_email
):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'user_emails': ['hello.ai']},
        )
        .add(uses=SecondExecutor)
    ) as f:
        with pytest.raises(Exception):
            f.index(
                inputs=Document(text='abc'),
                parameters={
                    'jwt': {
                        "token": 'another:test:ai:user:token',
                    }
                },
            )


def test_authorization_failed_api_key(auth_executor, admin_email):
    with (
        Flow()
        .config_gateway(
            uses=NOWGateway,
            protocol=['grpc'],
        )
        .add(
            uses=auth_executor,
            uses_with={'admin_emails': [admin_email]},
        )
        .add(uses=SecondExecutor)
    ) as f:
        with pytest.raises(Exception):
            f.index(
                inputs=Document(text='abc'), parameters={'api_key': 'invalid api_key'}
            )
