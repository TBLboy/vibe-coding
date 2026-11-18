def http_send(payload):
    if payload == 'timeout':
        raise TimeoutError()
    if not payload:
        raise ValueError('empty payload')
    return 'ok'
