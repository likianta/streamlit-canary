"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit Canary app.
"""

import streamlit_canary as sc


def main():
    sc.v3.Button('Start eye monitor', type='primary')


if __name__ == '__main__':
    sc.run(main, port=2203)
