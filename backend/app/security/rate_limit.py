"""Replaceable per-process rate limiter; AWS WAF provides distributed enforcement."""

import time
from collections import OrderedDict, deque


class RateLimiter:
    def __init__(self, limit: int, maximum_clients: int = 10000) -> None:
        self.limit, self.maximum_clients = limit, maximum_clients
        self.clients: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        requests = self.clients.setdefault(client, deque())
        self.clients.move_to_end(client)
        while requests and requests[0] <= now - 60:
            requests.popleft()
        if len(self.clients) > self.maximum_clients:
            self.clients.popitem(last=False)
        if len(requests) >= self.limit:
            return False
        requests.append(now)
        return True
