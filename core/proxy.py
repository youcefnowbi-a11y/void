"""VOIDFORGE :: Proxy rotation pool for HTTP requests.
Loads proxies from config/proxies.txt (one per line).
Supports: http://, https://, socks5:// (if PySocks installed).
Falls back to direct connection if no proxies configured."""
import os, random, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(HERE, "..", "config", "proxies.txt")


class ProxyPool:
    def __init__(self, path=None):
        self.proxies = []
        self._index = 0
        self._load(path or PROXY_FILE)

    def _load(self, path):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.proxies.append(line)

    @property
    def available(self):
        return len(self.proxies) > 0

    def next(self):
        """Round-robin proxy selection."""
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy

    def random(self):
        """Random proxy selection."""
        if not self.proxies:
            return None
        return random.choice(self.proxies)


# Singleton pool — loaded once at import time
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = ProxyPool()
    return _pool


def get_opener():
    """Returns a urllib opener configured with the next proxy, or None if no proxies."""
    pool = get_pool()
    if not pool.available:
        return None
    proxy_url = pool.next()
    proxy_handler = urllib.request.ProxyHandler({
        "http": proxy_url,
        "https": proxy_url,
    })
    return urllib.request.build_opener(proxy_handler)


def reload():
    """Reload proxy list from disk."""
    global _pool
    _pool = ProxyPool()
