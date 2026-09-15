"""Query PyPI (through the Tsinghua mirror) for a package's latest version.

Ported from the reference app's `package_query.py`.  The results table and
the code block are rendered with `v3.Text` instead of `st.table` /
`st.code`, and `packaging.version` is used instead of `semver`.
"""

import datetime
import json
import typing as tp
from urllib.request import Request
from urllib.request import urlopen

import streamlit_canary as sc
from lk_utils import fs
from lk_utils import now
from lk_utils import regex as re
from packaging.version import InvalidVersion
from packaging.version import Version

v3 = sc.v3

_HISTORY_FILE = fs.here('_package_query_history.json')

history = sc.Property[tp.Dict[str, tp.Dict[str, tp.Any]]](
    fs.load(_HISTORY_FILE, default=dict)
)
new_entries = sc.Property[tp.Set[str]](set())
package_name = sc.Property[str]('')
record = sc.Property[tp.Dict[str, tp.Any]]({})
busy_text = sc.Property[str]('')
status = sc.Property[str]('')


def ui() -> None:
    v3.Caption('Query PyPI latest version')

    with v3.Row(vertical_alignment='bottom'):
        with v3.TextInput(
            'Input package name', placeholder='e.g. request'
        ) as inp:

            @inp['on_value'].partial(sc._value)
            def _(name: str) -> None:
                name = name.strip()
                if name:
                    package_name.set(name)
                    _query(name, force=False)

        with v3.Button('Force refresh', type='primary') as btn:

            @btn.on_click
            def _force_refresh() -> None:
                name = package_name.get()
                if name:
                    _query(name, force=True)

    with v3.Button(
        'Save history', enabled=sc.bind(new_entries, lambda x: bool(x))
    ) as btn:

        @btn.on_click
        def _save_history() -> None:
            fs.dump(history.get(), _HISTORY_FILE)
            status.set(
                ':green[Newly saved {} records.]'.format(len(new_entries.get()))
            )
            new_entries.set(set())

    v3.Table(sc.bind(record, _format_record_rows))
    v3.Code(sc.bind(record, _format_pin))

    v3.Spinner(busy_text, visible=sc.bind(busy_text, lambda x: bool(x)))
    v3.Success(status, visible=sc.bind(status, lambda x: bool(x)))


# -----------------------------------------------------------------------------
# core


def _query(name: str, force: bool = False) -> None:
    if not force and name in history.get():
        record.set(history.get()[name])
        status.set('')
        return

    status.set('')
    busy_text.set('Querying PyPI...')
    try:
        data = _fetch_online(name)
    except Exception as e:
        status.set(':red[Query failed: {}]'.format(e))
        return
    finally:
        busy_text.set('')

    info = _extract_latest_package_info(data)
    history.get()[name] = info
    new_entries.set(new_entries.get() | {name})
    record.set(info)


def _fetch_online(name: str) -> dict:
    url = 'https://pypi.tuna.tsinghua.edu.cn/simple/{}'.format(name)
    req = Request(
        url, headers={'Accept': 'application/vnd.pypi.simple.v1+json'}
    )
    with urlopen(req, timeout=10) as rsp:
        return json.loads(rsp.read())


def _extract_latest_package_info(data: dict) -> tp.Dict[str, tp.Any]:
    latest_ver = _get_latest_version(data['versions'])

    def get_latest_files() -> tp.Iterator[dict]:
        yielded = False
        for f in data['files']:
            if '-{}'.format(latest_ver) in f['filename'] and re.search(
                r'-{}\W'.format(latest_ver), f['filename']
            ):
                yield f
                yielded = True
            elif yielded:
                break

    files = tuple(get_latest_files())
    filenames = tuple(f['filename'] for f in files)

    return {
        'name': data['name'],
        'version': latest_ver,
        'upload_time': max(
            (_cut_upload_time(x['upload-time']) for x in files), default=''
        ),
        'query_time': now(),
        'files': filenames,
        'tags': _get_tags(data['name'], latest_ver, filenames),
    }


# -----------------------------------------------------------------------------
# helpers


def _cut_upload_time(raw: str) -> str:
    # '2026-07-24T08:11:00.908914Z' -> '2026-07-24 08:11:00'
    return raw.split('.')[0].replace('T', ' ')


def _fix_version_form(origin: str) -> str:
    """
    examples:
        335          -> 335.0.0
        1.7          -> 1.7.0
        1.0.0b3      -> 1.0.0-b.3
        0.12.0.post2 -> 0.12.0-post.2
        6.4.0.1      -> 6.4.0-1
        21.7b0       -> 21.7.0-b.0
    """
    main, sub = (
        re.search(r'^(\d+(?:\.\d+)?(?:\.\d+)?)(.*)', origin).sure().groups()
    )

    if main.isdigit():
        main = '{}.0.0'.format(main)
    elif main.replace('.', '', 1).isdigit():
        main = '{}.0'.format(main)
    else:
        main = re.sub(r'\b0+([1-9])\b', r'\1', main)  # '0.12.01' -> '0.12.1'

    if sub:
        if sub.startswith('.'):
            sub = sub.lstrip('.')
        if re.search(r'([a-zA-Z]+)(\d+)', sub):
            sub = re.sub(
                r'([a-zA-Z]+)(\d+)', lambda x: '.'.join(x.groups()), sub
            )
        sub = '-{}'.format(sub)

    return main + sub


def _version_key(raw: str) -> Version:
    """PEP-440 parse, with a normalized fallback for odd version strings."""
    for candidate in (raw, _fix_version_form(raw)):
        try:
            return Version(candidate)
        except InvalidVersion:
            continue
    return Version('0')


def _get_latest_version(versions: tp.List[str]) -> str:
    return max(versions, key=_version_key)


def _get_tags(
    package_name: str, version: str, filenames: tp.Iterable[str]
) -> tp.List[str]:
    tags: tp.Set[str] = set()
    for filename in filenames:
        found = re.fullmatch(
            r'{}-{}(?:-(.+))?(?:\.whl|\.tar\.gz|\.zip)'.format(
                package_name.lower().replace('-', '[-_]'), version
            ),
            filename.lower(),
        )
        if found is None:
            continue
        if found.group(1):
            tags.update(found.group(1).split('-'))
    tags.discard('none')
    return sorted(tags)


def _time_delta(time_str: str) -> str:
    try:
        time_old = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return ''
    seconds = int((datetime.datetime.now() - time_old).total_seconds())
    for unit, span in (
        ('year', 31536000),
        ('month', 2592000),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
    ):
        if seconds >= span:
            number = seconds // span
            return '{} {}{} ago'.format(number, unit, 's' if number > 1 else '')
    return 'just now'


def _format_record_rows(
    rec: tp.Dict[str, tp.Any],
) -> tp.List[tp.Tuple[str, str]]:
    """Render the record as `(key, value)` rows (mirrors `st.table`)."""
    if not rec:
        return []
    return [
        ('name', rec.get('name', '')),
        ('version', rec.get('version', '')),
        (
            'upload_time',
            '{} :gray[({})]'.format(
                rec.get('upload_time', ''),
                _time_delta(rec.get('upload_time', '')),
            ),
        ),
        ('query_time', rec.get('query_time', '')),
        ('tags', '; '.join(rec.get('tags', []))),
    ]


def _format_pin(rec: tp.Dict[str, tp.Any]) -> str:
    if not rec:
        return ''
    return '"{}>={}",'.format(rec.get('name', ''), rec.get('version', ''))
