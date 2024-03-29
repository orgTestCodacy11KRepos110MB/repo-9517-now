# -*- coding: utf-8 -*-
"""
common prompt functionality
"""
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator


def if_mousedown(handler):
    def handle_if_mouse_down(mouse_event):
        if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
            return handler(mouse_event)
        else:
            return NotImplemented

    return handle_if_mouse_down


# TODO probably better to use base.Condition
def setup_validator(kwargs):
    # this is an internal helper not meant for public consumption!
    # note this works on a dictionary
    validate_prompt = kwargs.pop('validate', None)
    if validate_prompt:
        if issubclass(validate_prompt, Validator):
            kwargs['validator'] = validate_prompt()
        elif callable(validate_prompt):

            class _InputValidator(Validator):
                def validate(self, document):
                    # print('validation!!')
                    verdict = validate_prompt(document.text)
                    if isinstance(verdict, str):
                        raise ValidationError(
                            message=verdict, cursor_position=len(document.text)
                        )
                    elif verdict is not True:
                        raise ValidationError(
                            message='invalid input', cursor_position=len(document.text)
                        )

            kwargs['validator'] = _InputValidator()
        return kwargs['validator']


def setup_simple_validator(kwargs):
    # this is an internal helper not meant for public consumption!
    # note this works on a dictionary
    # this validates the answer not a buffer
    # TODO
    # not sure yet how to deal with the validation result:
    # https://github.com/jonathanslenders/python-prompt-toolkit/issues/430
    validate = kwargs.pop('validate', None)
    if validate is None:

        def _always(answer):
            return True

        return _always
    elif not callable(validate):
        raise ValueError('Here a simple validate function is expected, no class')

    def _validator(answer):
        verdict = validate(answer)
        if isinstance(verdict, str):
            raise ValidationError(message=verdict)
        elif verdict is not True:
            raise ValidationError(message='invalid input')

    return _validator


# FIXME style defaults on detail level
default_style = Style.from_dict(
    {
        'separator': '#6C6C6C',
        'questionmark': '#5F819D',
        'selected': '',  # default
        'pointer': '#FF9D00 bold',  # AWS orange
        'instruction': '',  # default
        'answer': '#FF9D00 bold',  # AWS orange
        'question': 'bold',
    }
)
