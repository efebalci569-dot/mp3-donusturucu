import threading
import time


class Lifecycle:
    # Sekme kapanınca uygulama kendini kapatsın. idle_timeout, tarayıcıların arka
    # plandaki sekmelerde zamanlayıcıları dakikada bire düşürmesine karşı pay bırakır.
    def __init__(self, clock=time.monotonic, grace=120.0, idle_timeout=180.0):
        self._clock = clock
        self._grace = grace
        self._idle_timeout = idle_timeout
        self._started = clock()
        self._last_beat = None
        self._lock = threading.Lock()

    def heartbeat(self):
        with self._lock:
            self._last_beat = self._clock()

    def should_exit(self, active_jobs):
        if active_jobs > 0:
            return False
        with self._lock:
            now = self._clock()
            if self._last_beat is None:
                return now - self._started > self._grace
            return now - self._last_beat > self._idle_timeout
