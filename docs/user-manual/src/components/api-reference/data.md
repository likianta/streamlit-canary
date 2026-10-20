# Data Elements

## `Table`

A static table. `rows` is a sequence of rows, and the first cell of each
row is rendered as a row header (`<th scope="row">`).

```python
sc.Table(
    rows=[
        ('Alice', 'Engineering', 'alice@example.com'),
        ('Bob', 'Design', 'bob@example.com'),
    ],
    header=('Name', 'Team', 'Email'),
    caption='Team directory',
    footer='3 people',
)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `rows` | sequence of sequences | Body rows |
| `header` | sequence of strings | Optional header row |
| `caption` | `str` | Caption above the table |
| `footer` | `str` | Footer below the table |
| `header_background` | `bool` | Draw a background behind the header |
| `title` | `str` | Optional table title |
| `visible` | `bool \| Property \| 'auto'` | Default `'auto'` |

Properties: `rows`.

The table is static in the DOM: to update it, set a new `rows` value. The
row header cell is useful for a matrix-like table where the first column
labels the row.

Markdown color markers such as `:red[overdue]` work inside cells.

An empty `rows` value hides the table when `visible='auto'`.
