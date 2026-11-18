def legacy(value):
    if not isinstance(value, (int, float)):
        raise ValueError('not numeric')
    return max(0, value)
