import streamlit as st
import typing as tp

def row(
    vertical_alignment: tp.Literal['top', 'center', 'bottom'] = 'top',
    border: bool = False,
):
    return st.container(
        border=border, horizontal=True, vertical_alignment=vertical_alignment
    )
