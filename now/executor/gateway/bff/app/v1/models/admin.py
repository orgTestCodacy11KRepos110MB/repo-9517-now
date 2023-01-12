from typing import List

from pydantic import Field

from now.executor.gateway.bff.app.v1.models.shared import BaseRequestModel


class UpdateEmailsRequestModel(BaseRequestModel):
    user_emails: List[str] = Field(
        default=...,
        description='List of user emails who are allowed to access the flow',
    )


class UpdateApiKeysRequestModel(BaseRequestModel):
    api_keys: List[str] = Field(
        default=...,
        description='List of api keys which allow to access the flow in an automated way',
    )
