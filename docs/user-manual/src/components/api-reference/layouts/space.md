# Space

A flexible spacer.

```python
with sc.Row():
    sc.IconButton('home')
    sc.Space(size='stretch')
    sc.Popover(':material/bucket_check: 0')
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `size` | size keyword | Alias of `width` |
| `width` | size keyword | The spacer's width |

Properties: `visible`.

Inside a `Row`, a stretching `Space` absorbs the leftover width, pushing
everything after it to the right edge. In a vertical container there is no
leftover width to absorb, so it renders nothing.

`size` is the spelling used by `st.space`. `Space(size='stretch')` and
`Space(width='stretch')` are the same spacer, and passing both raises an
error.
