import typing as tp
from functools import partial

import streamlit as st
from lk_utils import uuid

from .binding import Binding
from ..session import SessionDataV2


class T:
    NeverOtherType = tp.Any
    #   it indicates that the type should never be used. we use it inside
    #   tp.Union type, to pacify type checker not be annoyed by external callers
    #   when they pass an "incorrect type".
    #   for example, tp.Union[str, NeverOtherType] means this parameter accepts
    #   only str, but if external caller passes other type, the type checker
    #   won't complain about this. but we should review the detailed type in
    #   actual implementation.


class _BaseComponent:
    key: str
    result: tp.Any
    _value_holder: tp.Optional[SessionDataV2]

    # def __init__(
    #     self, key: str, component_name, bidirectional_data, *args, **kwargs
    # ):
    #     self.key = key
    #     self.result = getattr(st, component_name)(*args, **kwargs)

    def _set_value(self) -> None:
        # assert self._value_holder is not None
        self._value_holder.set(st.session_state[self.key])


class SelectBox(_BaseComponent):
    def __init__(
        self,
        label: str,
        options: tp.Union[tp.Sequence, SessionDataV2] = (),
        index: int = 0,
        *,
        bind: tp.Union[bool, SessionDataV2, T.NeverOtherType] = False,
        format_func: tp.Callable[[tp.Any], str] = str,
        **kwargs,
    ) -> None:
        is_v2 = isinstance(options, SessionDataV2)
        plain_value = options.get() if is_v2 else options
        self.key = _generate_key(
            label, plain_value, index, options.generation if is_v2 else None
        )
        if bind:
            if isinstance(bind, SessionDataV2):
                self._value_holder = bind
            else:
                assert isinstance(options, SessionDataV2)
                self._value_holder = options
            kwargs['on_change'] = self._set_value
        self.result = st.selectbox(
            label,
            plain_value,
            key=self.key,
            index=index,
            format_func=format_func,
            **kwargs,
        )


class TextInput(_BaseComponent):
    def __init__(
        self,
        label: str,
        value: tp.Union[str, SessionDataV2] = '',
        *,
        bind: bool = False,
        placeholder: tp.Optional[str] = None,
        **kwargs,
    ) -> None:
        is_v2 = isinstance(value, SessionDataV2)
        plain_value = value.get() if is_v2 else value
        self.key = _generate_key(
            label, plain_value, placeholder, value.generation if is_v2 else None
        )
        if bind:
            assert isinstance(value, SessionDataV2)
            self._value_holder = value
            kwargs['on_change'] = self._set_value
        self.result = st.text_input(
            label, plain_value, key=self.key, placeholder=placeholder, **kwargs
        )


# def _deduce_key(component_name, *args, **kwargs) -> str:
#     func = getattr(st, component_name)
#     key_factors = []
#     if len(args) == 0:
#         if component_name in ('selectbox',):
#             key_factors.append(kwargs['label'])
#             key_factors.append(kwargs['options'])
#         elif component_name in ('text_input',):
#             key_factors.append(kwargs['text'])
#             key_factors.append(kwargs['value'])

#         for i, (k, p) in enumerate(
#             inspect.signature(func).parameters.items()
#         ):
#             ...


def _generate_key(*factors: tp.Any) -> str:
    return uuid(':'.join(map(str, factors)))


# ------------------------------------------------------------------------------
# DELETE


def _generic_component_wrapper(component_name, *args, **kwargs) -> Binding:
    key_factors = []
    if len(args) == 0:
        key_factors.extend(tuple(kwargs.values())[:2])
    elif len(args) == 1:
        key_factors.append(args[0])
        if kwargs:
            key_factors.append(tuple(kwargs.values())[0])
        else:
            key_factors.append('')
    else:
        key_factors.extend(args[:2])
    assert len(key_factors) == 2
    key = _generate_key(*key_factors)
    binding = Binding(key)
    binding.value = getattr(st, component_name)(
        *args, **kwargs, key=key, on_change=binding.trigger
    )
    return binding


selectbox = partial(_generic_component_wrapper, 'selectbox')
text_input = partial(_generic_component_wrapper, 'text_input')
