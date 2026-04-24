class UniqueKeyGenerator:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def __call__(self, *args) -> str:
        return '{}:{}'.format(self._prefix, ':'.join(args))
