from transport import http_send

class Service:
    def __init__(self):
        self.sent = set()

    def submit(self, order_id, payload):
        if order_id in self.sent:
            return 'duplicate'
        try:
            http_send(payload)
        except TimeoutError:
            return 'retryable'
        except ValueError:
            return 'terminal'
        self.sent.add(order_id)
        return 'accepted'
