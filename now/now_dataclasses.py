"""
This module implements a command-line dialog with the user.
Its goal is to configure a UserInput object with users specifications.
Optionally, values can be passed from the command-line when jina-now is launched. In that case,
the dialog won't ask for the value.
"""
from __future__ import annotations, print_function, unicode_literals

import dataclasses
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel, StrictBool

from now.constants import DatasetTypes


class UserInput(BaseModel):
    app_instance: Optional['JinaNOWApp'] = None  # noqa: F821
    # data related
    flow_name: Optional[str] = None
    dataset_type: Optional[DatasetTypes] = None
    dataset_name: Optional[str] = None
    dataset_url: Optional[str] = None
    dataset_path: Optional[str] = None

    # AWS related
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region_name: Optional[str] = None

    # Fields
    index_fields: Optional[List] = []
    index_field_candidates_to_modalities: Optional[Dict[str, TypeVar]] = {}
    filter_fields: Optional[List] = []
    filter_field_candidates_to_modalities: Optional[Dict[str, str]] = {}
    field_names_to_dataclass_fields: Optional[Dict] = {}

    # ES related
    es_index_name: Optional[str] = None
    es_host_name: Optional[str] = None
    es_additional_args: Optional[Dict] = None

    # cluster related
    cluster: Optional[str] = None
    secured: Optional[StrictBool] = None
    jwt: Optional[Dict[str, str]] = None
    admin_name: Optional[str] = None
    admin_emails: Optional[List[str]] = None
    user_emails: Optional[List[str]] = None
    additional_user: Optional[StrictBool] = None
    api_key: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


@dataclasses.dataclass
class DialogOptions:
    name: str
    prompt_message: str
    prompt_type: str
    choices: Union[
        List[Dict[str, Union[str, bool]]],
        Callable[[Any], List[Dict[str, str]]],
    ] = None
    is_terminal_command: StrictBool = (
        False  # set when this dialog is required as a cli param
    )
    argparse_kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)
    description: str = None  # Description to show on terminal when used as a cli param
    depends_on: Optional['DialogOptions', StrictBool] = None
    conditional_check: Callable[[Any], bool] = None
    post_func: Callable[[Any], None] = None


if TYPE_CHECKING:
    from now.app.base.app import JinaNOWApp

    UserInput.update_forward_refs()
