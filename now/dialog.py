"""
This module implements a command-line dialog with the user.
Its goal is to configure a UserInput object with users specifications.
Optionally, values can be passed from the command-line when jina-now is launched. In that case,
the dialog won't ask for the value.
"""
from __future__ import annotations, print_function, unicode_literals

import inspect
import pathlib

import now.utils
from now.common import options
from now.common.options import construct_app
from now.constants import Apps
from now.now_dataclasses import DialogOptions, UserInput
from now.utils import RetryException

cur_dir = pathlib.Path(__file__).parent.resolve()


def configure_user_input(**kwargs) -> UserInput:
    user_input = UserInput()
    now.utils.print_headline()
    # Create the search app.
    # TODO: refactor this when more apps are added
    user_input.app_instance = construct_app(Apps.SEARCH_APP)
    # Ask the base/common options
    for option in options.base_options:
        if inspect.isfunction(option):
            for result in option(user_input, **kwargs):
                configure_option(result, user_input, **kwargs)
        else:
            configure_option(option, user_input, **kwargs)
    # Ask app specific options
    for option in user_input.app_instance.options:
        configure_option(option, user_input, **kwargs)

    return user_input


def configure_option(option: DialogOptions, user_input: UserInput, **kwargs):
    # Check if it is dependent on some other dialog options
    if option.depends_on and not option.conditional_check(user_input):
        return

    # Populate choices if needed
    if option.choices and inspect.isfunction(option.choices):
        option.choices = option.choices(user_input, **kwargs)

    while True:
        val = now.utils.prompt_value(
            **option.__dict__,
            **kwargs,
        )

        if val:
            kwargs[option.name] = val
            if hasattr(user_input, option.name):
                setattr(user_input, option.name, val)

        try:
            # If there is any post function then invoke that
            if inspect.isfunction(option.post_func):
                option.post_func(user_input, **kwargs)
        except RetryException as e:
            print(e)
            continue
        break

    return val
