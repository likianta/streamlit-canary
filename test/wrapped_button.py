import streamlit as st
import streamlit_swift as sw


def main():
    with sw.Button('Click me') as btn:
        @btn.on_click
        def _():
            with _placeholder:
                st.write('Button clicked!')
        with sw.Empty() as _placeholder:
            pass


if __name__ == '__main__':
    sw.run(main)
