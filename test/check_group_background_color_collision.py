import streamlit_canary as sc

def main():
    sc.CheckGroup(
        'Check group',
        ('Option 1', 'Option 2', 'Option 3'),
    )
    sc.CheckGroup(
        'Check group',
        ('Option 4', 'Option 5', 'Option 6'),
        horizontal=True,
    )

if __name__ == '__main__':
    sc.run(main, port=2201)
