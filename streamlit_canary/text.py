import re
import typing as tp
from functools import partial

_MARK_START = re.compile(r':[a-zA-Z]+\[')


def _mark_end(src: str, from_: int) -> int:
    """Index of the `]` that closes the `:name[..]` mark opened at `from_`,
    or -1 when nothing closes it.

    Mirrors `scMarkEnd` in `50-markdown.js`: the closing bracket is the one
    that *balances* -- a `:red[..]` nested inside counts as one bracket pair
    -- and a backslash escapes the next character, which is how a literal
    bracket is written.
    """
    depth = 1
    i = from_
    while i < len(src):
        ch = src[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _escape_brackets(text: str) -> str:
    """Escape the `[` / `]` that are plain text, leaving the brackets of a
    nested `:name[..]` mark (and existing backslash escapes) alone.

    `:color[..]` is parsed by bracket *balance*, so a raw `]` in the wrapped
    text ends the mark early while a raw `[` makes it swallow whatever
    follows. Escaping both -- but only where they are not a mark of their own
    -- keeps the mark balanced and lets a nested `:red[..]` survive.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = _MARK_START.match(text, i)
        if m is not None:
            end = _mark_end(text, m.end())
            if end >= 0:
                # a nested mark: keep it whole, brackets and all
                out.append(text[i : end + 1])
                i = end + 1
                continue
        ch = text[i]
        if ch == '\\':
            out.append(text[i : i + 2])
            i += 2
        elif ch in '[]':
            out.append('\\' + ch)
            i += 1
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def colorize(item: tp.Any, color: str) -> str:
    """Wrap `item` in a `:color[..]` mark: `sc.blue('Go')` -> `':blue[Go]'`.

    The text is *marked up* rather than merely bracketed, for two reasons:

    - the mark closes on bracket balance (see `_escape_brackets`), so a `]`
      that happens to sit in the text -- `0xF102[3:0]`, say -- must not be
      left to end it early;
    - a mark never spans a blank line, where markdown starts a fresh
      paragraph, so a multi-line text is marked one line at a time. Each line
      keeps the colour and blank lines still separate paragraphs.
    """
    parts: list[str] = []
    for line in str(item).split('\n'):
        if line.strip():
            line = ':{}[{}]'.format(color, _escape_brackets(line))
        parts.append(line)
    return '\n'.join(parts)


def bold(item: tp.Any) -> str:
    """Wrap `item` in markdown bold: `sc.bold('Go')` -> `'**Go**'`.

    Composes with the color shorthands, e.g.
    `sc.blue(sc.bold('Connect'))` -> `':blue[**Connect**]'`.
    """
    return '**{}**'.format(item)


blue = partial(colorize, color='blue')
dim = partial(colorize, color='gray')
gray = partial(colorize, color='gray')
green = partial(colorize, color='green')
magenta = partial(colorize, color='magenta')
orange = partial(colorize, color='orange')
red = partial(colorize, color='red')
yellow = partial(colorize, color='yellow')
