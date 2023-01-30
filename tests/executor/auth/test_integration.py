import json

import pytest
from docarray import Document

from now.executor.abstract.auth.auth import (
    SecurityLevel,
    get_auth_executor_class,
    secure_request,
)


@pytest.fixture
def executor_class():
    AuthExecutor = get_auth_executor_class()

    class E(AuthExecutor):
        @secure_request(level=SecurityLevel.USER, on='/index')
        def index(self, *args, **kwargs):
            print('do something')

    return E


def test_executor_persistence(executor_class, tmpdir):
    api_key = 'my_key'
    e = executor_class(api_keys=[api_key], metas={'workspace': tmpdir})
    e.update_user_emails(
        parameters={'api_key': api_key, 'user_emails': ['abc@test.ai']}
    )
    with open(e.user_emails_path, 'r') as fp:
        json.load(fp)
    e.update_api_keys(parameters={'api_key': api_key, 'api_keys': ['your_key']})
    with open(e.user_emails_path, 'r') as fp:
        json.load(fp)


def test_authorization_success_api_key(executor_class, admin_email):
    executor = executor_class(user_emails=['hello.ai'], api_keys=['valid_key'])
    executor.index(docs=Document(text='abc'), parameters={'api_key': 'valid_key'})


def test_authorization_failed(executor_class, admin_email):
    executor = executor_class(user_emails=['hello.ai'])
    with pytest.raises(Exception):
        executor.index(
            docs=Document(text='abc'),
            parameters={'jwt': {'token': 'invalid token of abc.def@jina.ai'}},
        )


def test_authorization_successful(executor_class, admin_email, mock_hubble_admin_email):
    executor = executor_class(user_emails=['hello.ai'])
    executor.index(
        docs=Document(text='abc'),
        parameters={
            'jwt': {
                "token": 'yet:another:admin:token',
            }
        },
    )


def test_authorization_success_jina_users(executor_class, mock_hubble_user_email):
    executor = executor_class(user_emails=['hello.ai'])
    executor.index(
        docs=Document(text='abc'),
        parameters={
            'jwt': {
                "token": 'another:jina:ai:user:token',
            }
        },
    )


def test_authorization_failed_domain_users(
    executor_class, mock_hubble_domain_user_email
):
    executor = executor_class(user_emails=['hello.ai'])
    with pytest.raises(Exception):
        executor.index(
            docs=Document(text='abc'),
            parameters={
                'jwt': {
                    "token": 'another:test:ai:user:token',
                }
            },
        )


def test_authorization_failed_api_key(executor_class, admin_email):
    executor = executor_class(user_emails=['hello.ai'])
    with pytest.raises(Exception):
        executor.index(
            docs=Document(text='abc'), parameters={'api_key': 'invalid api_key'}
        )
