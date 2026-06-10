import typing as tp
from inspect import currentframe
from types import FrameType


class UniqueKeyGenerator:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def __call__(self, *args) -> str:
        return '{}:{}'.format(self._prefix, ':'.join(args))


def generate_unique_key(
    prefix: str = '', _frame: tp.Optional[FrameType] = None
) -> str:
    frame = _frame or tp.cast(FrameType, currentframe().f_back.f_back)
    uid = (prefix and prefix + ':') + '{}:{}'.format(
        frame.f_code.co_filename, frame.f_lineno
    )
    return uid
