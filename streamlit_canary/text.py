import re
import sys
import typing as tp
from functools import partial

_MARK_START = re.compile(r':[a-zA-Z]+\[')

# Font stacks for `font_family=sc.MONOSPACED`. The browser walks the list in
# order and takes the first family the *viewer's* machine has, so the split by
# platform only decides what to try first -- and every stack ends in the
# generic `monospace` keyword, which always resolves to something.
#
# Windows: "Cascadia Code" is what Windows Terminal defaults to and what ships
# with Windows 11 (on 10 it comes with the Terminal app, so a plain 10 may not
# have it). `Consolas` is the fallback -- the monospace every Windows since
# Vista installs, and what the generic keyword resolves to as well.
# macOS: `ui-monospace` is the system UI monospace (SF Mono) -- the family
# macOS itself uses for monospaced text -- then the two it has shipped for
# years. `SF Mono` is spelled out too because not every browser knows the
# keyword, though the font is not one users can pick in Font Book.
# Linux: no single default across distros. DejaVu Sans Mono is the one nearly
# every distro installs; Liberation Mono and Noto Sans Mono cover most of the
# rest, and the keyword takes whatever the desktop configured.
# the multi-word names are quoted with single quotes: the value travels into
# an HTML `style` attribute, which is delimited by double quotes (and would be
# ended early by one inside).
_MONOSPACED_STACKS = {
    'darwin': "ui-monospace, 'SF Mono', Menlo, Monaco, monospace",
    'win32': "'Cascadia Code', Consolas, monospace",
}
_MONOSPACED_LINUX = (
    "'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', monospace"
)

MONOSPACED = _MONOSPACED_STACKS.get(sys.platform, _MONOSPACED_LINUX)

# The size that belongs with `MONOSPACED`: a text element drawing in it also
# gets this `font-size` (see `render.py`'s `_text_style`), unless the caller
# passed a `font_size` of their own.
#
# A monospace face is drawn larger on its em than a proportional one, so at the
# same pixel size it reads bigger. Measured against this page's font (Source
# Sans) at 160px, 'Cascadia Code' has a ~6% taller x-height and a ~39% wider
# advance -- the width is what dominates, which is why a monospaced paragraph
# looks heavier even when the letters are barely taller. `0.875em` is the code
# size Streamlit's own themes use, i.e. code set one step below prose; it also
# brings the x-height back to within a few percent of the body text (0.94em
# would match it exactly).
MONOSPACED_SIZE = '0.875em'


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
