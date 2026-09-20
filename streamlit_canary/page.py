import typing as t

from ._streamlit import st

if t.TYPE_CHECKING:
    from streamlit.navigation.page import StreamlitPage


def pages(
    elements: t.Dict[str, t.Callable[[], t.Any]]
) -> 'StreamlitPage':
    normalized_elements = []
    for k, v in elements.items():
        normalized_elements.append(st.Page(
            v,
            title=k,
            url_path=k.lower().replace(' ', '-'),
        ))
    return st.navigation(normalized_elements)
