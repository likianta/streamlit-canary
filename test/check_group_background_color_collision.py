import streamlit_canary as sc

v3 = sc.v3


def main():
    v3.CheckGroup(
        'Check group',
        ('Option 1', 'Option 2', 'Option 3'),
        full_body_click=False,
    )
    v3.CheckGroup(
        'Check group',
        ('Option 4', 'Option 5', 'Option 6'),
        full_body_click=False,
        horizontal=True,
    )


if __name__ == '__main__':
    sc.run(main, port=2201)
