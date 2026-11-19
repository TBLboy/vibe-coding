NEXT = {'prepare': 'implement', 'implement': 'verify', 'verify': 'complete'}

def transition(state, target):
    if state not in NEXT or NEXT[state] != target:
        raise ValueError('illegal transition')
    return target
