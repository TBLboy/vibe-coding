from strategies import legacy

STRATEGIES = {'legacy': legacy}

def evaluate(value, strategy=None):
    key = 'legacy' if strategy is None else strategy
    if key not in STRATEGIES:
        raise ValueError('unknown strategy')
    return STRATEGIES[key](value)
