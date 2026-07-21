import streamlit as st
import streamlit_canary as sc
from neoprint import print


@sc.init_state
class State:
    link_format = '![](.images/{ymdhns}.png)'
    __version__ = 1


def main():
    print(State.link_format, ':i')
    with sc.row():
        sc.v2.text_input('Input', State.link_format)
        sc.v2.selectbox(
            'Link format',
            (
                '![](.images/{ymdhns}.png)',
                '![](./.images/{ymdhns}.png)',
                '![](.images/{filename_hash}-{hns}.png)',
            ),
        ).bind(State, 'link_format')


if __name__ == '__main__':
    main()
