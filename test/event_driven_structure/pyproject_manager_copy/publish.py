"""Publish helpers (mirrors the reference app's `publish.py`)."""

import requests
from lk_utils import fs
from neoprint import print


def publish_to_private_index(dist_file: str) -> None:
    url = 'http://{}/{}/{}'.format(
        'localhost:2132',
        fs.filename(dist_file).split('-')[0].replace('_', '-'),
        fs.filename(dist_file),
    )
    print(url, ':vs')
    with open(dist_file, 'rb') as f:
        requests.put(url, data=f)
