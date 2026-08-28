import typing as tp
from functools import partial


def colorize(item: tp.Any, color: str) -> str:
    return ':{}[{}]'.format(color, str(item).replace('[', '\\['))


blue = partial(colorize, color='blue')
dim = partial(colorize, color='gray')
gray = partial(colorize, color='gray')
green = partial(colorize, color='green')
magenta = partial(colorize, color='magenta')
orange = partial(colorize, color='orange')
red = partial(colorize, color='red')
yellow = partial(colorize, color='yellow')
