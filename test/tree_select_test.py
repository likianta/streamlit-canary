import neoprint as np
import streamlit as st

import streamlit_canary as sc


def main():
    np.show(':i')

    result = sc.tree_select(
        start_directory='streamlit_canary', filter='.py', node_type='file'
    )
    np.show('single select', result)

    # st.radio('Test radio', ('a', 'b', 'c'), horizontal=True, index=-1)

    # result = sc.tree_select_with_input(
    #     'Select a Python script',
    #     initial_path='streamlit_canary',
    #     filter='.py',
    #     node_type='file',
    #     # callback=lambda path: np.show(':v2', path),
    # )
    # np.show(result, ':v2i1n' if result else ':vi1n')


if __name__ == '__main__':
    # strun 3001 test/tree_select_test.py
    main()
