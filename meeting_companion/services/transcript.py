from __future__ import annotations

import math
from collections import deque

from .models import Entry


class TranscriptAccumulator:
    """Replace interim hypotheses; only final SDK speech becomes durable text."""

    def __init__(self):
        self.partial = ""
        self.seen: set[tuple] = set()
        self.order: deque = deque()

    def accept(self, text, final, start, end, identity, offset, elapsed) -> Entry | None:
        if not final:
            self.partial = text
            return None
        self.partial = ""
        if not text:
            return None
        valid_start = isinstance(start, (float, int)) and math.isfinite(start) and start >= 0
        valid_end = isinstance(end, (float, int)) and math.isfinite(end) and end >= 0
        key = ("id", identity) if identity else (("time", start, end, text) if valid_start else None)
        if key is not None:
            if key in self.seen:
                return None
            self.seen.add(key)
            self.order.append(key)
            if len(self.order) > 4096:
                self.seen.discard(self.order.popleft())
        # Anonymous, untimed finals cannot safely be deduplicated by text: people repeat words.
        seconds = offset + start if valid_start else elapsed
        return Entry(max(0, seconds), text, offset + end if valid_end else None)
