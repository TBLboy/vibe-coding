class Store:
    def __init__(self, state='prepare'):
        self.state = state
        self.writes = 0
    def write(self, state):
        self.state = state
        self.writes += 1

def handle(store, target):
    # Defective production path: does not use machine.transition.
    store.write(target)
    return target
