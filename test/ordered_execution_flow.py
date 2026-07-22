
from neoprint import print

import streamlit_canary as sc


@sc.init_state_v2
class State:
    link_format = '![](.images/{ymdhns}.png)'
    __version__ = 8


def main():
    print(State.link_format, ':i')
    with sc.row():
        sc.v2.TextInput('Input', State.link_format)
        sc.v2.SelectBox(
            'Link format',
            (
                '![](.images/{ymdhns}.png)',
                '![](./.images/{ymdhns}.png)',
                '![](.images/{filename_hash}-{hns}.png)',
            ),
            # bind=tp.cast(SessionDataV2, State.link_format),
            bind=State.link_format,
        )


if __name__ == '__main__':
    main()
