import typing as tp

from ._streamlit import st

if tp.TYPE_CHECKING:
    from streamlit.navigation.page import StreamlitPage


def pages(elements: tp.Dict[str, tp.Callable[[], tp.Any]]) -> 'StreamlitPage':
    normalized_elements = []
    for k, v in elements.items():
        normalized_elements.append(
            st.Page(v, title=k, url_path=k.lower().replace(' ', '-'))
        )
    return st.navigation(normalized_elements)
