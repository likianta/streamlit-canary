"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit Canary app.
"""

import streamlit_canary as sc


def main():
    sc.v3.Button('Start eye monitor', type='primary')
    sc.v3.Table(
        (
            ('Link status', ':green[ON]'),
            ('PRBS error counter', ':red[123]'),
            ('Server connected', 'Fake device'),
        ),
        width='content',
    )
    sc.v3.Table(
        (
            ('File name', 'droo1.mat'),
            ('File size', '28.19KB'),
            ('MATLAB version', '7.3'),
        ),
        width='stretch',  # default
    )


if __name__ == '__main__':
    sc.run(main, port=2203)
