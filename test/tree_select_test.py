from neoprint import print

import streamlit_canary as sc


def main() -> None:
    print(':dvi')

    # result = sc.tree_select(
    #     start_directory='streamlit_canary', filter='.py', node_type='file'
    # )
    # print('single select', result)

    # st.radio('Test radio', ('a', 'b', 'c'), horizontal=True, index=-1)

    result = sc.tree_select_with_input(
        'Select a folder',
        initial_path='streamlit_canary',
        # filter='.py',
        node_type='folder',
        # callback=lambda path: np.show(':v2', path),
    )
    print(result, ':v2i1n' if result else ':v1i1n')


if __name__ == '__main__':
    # strun 3001 test/tree_select_test.py
    main()
