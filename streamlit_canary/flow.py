class PostEvents:
    """
    knowledge: docs.streamlit.io/get-started/fundamentals/main-concepts#data-flow
    """
    
    def __init__(self):
        self._events = []
        
    def append(self, func):
        self._events.append(func)
        
    # def collect(self):
    #     pass
        
    def execute(self):
        for func in self._events:
            func()
        self._events.clear()


post_events = PostEvents()
