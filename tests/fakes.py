"""Isolated test doubles. Production code never imports this module."""
import queue
import time
from types import SimpleNamespace


class FakeSDKSession:
    def __init__(self):
        self.results = queue.Queue()
        self.settings = SimpleNamespace()
        self.started = self.stopped = False
        self.chunks = []

    def start(self):
        self.started = True

    def append(self, pcm):
        self.chunks.append(pcm)

    def emit(self, text="Unit-test fixture", final=True, identity="segment", start=0):
        self.results.put(SimpleNamespace(content=[SimpleNamespace(text=text)], is_final=final,
                                         start_time=start, end_time=start + 1, id=identity))

    def get_stream(self):
        while True:
            result = self.results.get()
            if result is None:
                break
            if isinstance(result, Exception):
                raise result
            yield result

    def stop(self):
        self.stopped = True
        self.emit("Tail fixture", identity="tail", start=2)
        self.results.put(None)


class FakeClient:
    def __init__(self):
        self.sessions = []
        self.unloaded = False

    def create_session(self):
        session = FakeSDKSession()
        self.sessions.append(session)
        return session

    def unload(self):
        self.unloaded = True


class FakePipeline:
    instances = []

    def __init__(self, settings, output, notify):
        self.output = output
        self.error = None
        self.started = self.stopped = False
        self.instances.append(self)

    def start(self):
        self.started = True
        self.epoch = time.monotonic()
        self.output.put(b"\0" * 640)

    def stop(self):
        self.stopped = True


def until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    assert predicate(), "Timed out waiting for the background operation"
