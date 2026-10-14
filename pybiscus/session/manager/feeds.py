from collections import deque
from threading import Lock

# enough for a long session; beyond, the oldest messages are dropped, and only a page opened that
# late misses them
FEED_LENGTH = 20000


class Feed:
    """messages kept for every reader, each polling with its own cursor: a read used to empty the
    list, so two pages of the same session (two viewers, a viewer and a recorder) each showed part
    of the logs and of the curves"""

    def __init__(self, length: int = FEED_LENGTH):
        self._items = deque(maxlen=length)
        self._next = 0
        self._lock = Lock()

    def append(self, item) -> None:
        with self._lock:
            self._items.append((self._next, item))
            self._next += 1

    def read(self, since: int) -> dict:
        with self._lock:
            return {"items": [item for seq, item in self._items if seq >= since], "next": self._next}

    def clear(self) -> None:
        # the numbering goes on: the readers' cursors stay valid
        with self._lock:
            self._items.clear()
