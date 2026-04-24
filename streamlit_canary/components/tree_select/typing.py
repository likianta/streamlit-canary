import typing as tp


class T:
    Filter = tp.Optional[tp.Union[str, tp.Tuple[str, ...]]]
    NodeType = tp.Literal['file', 'folder', 'both']
    # SingleSelectResult = tp.Optional[tp.Tuple[str, bool]]  # Tuple[path, is_dir]
    SingleSelectResult = str
    #   for non-result, returns ''.
    #   if you set node type to 'both', you need to check if it dir or file by 
    #   yourself.
    MultiSelectResult = tp.Optional[tp.Sequence[str]]
