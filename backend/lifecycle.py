import threading
import time


class Lifecycle:
    # Sekme kapanınca uygulama kendini kapatsın. idle_timeout, tarayıcıların arka
    # plandaki sekmelerde zamanlayıcıları dakikada bire düşürmesine karşı pay bırakır.
    # wake_gap: iki kontrol arası bundan uzunsa bilgisayar uykudan uyanmıştır (Windows'ta
    # time.monotonic uykuda da sayar); açık sekmeye heartbeat gönderme fırsatı verilir.
    def __init__(self, clock=time.monotonic, grace=120.0, idle_timeout=180.0, wake_gap=30.0):
        self._clock = clock
        self._grace = grace
        self._idle_timeout = idle_timeout
        self._wake_gap = wake_gap
        self._started = clock()
        self._last_beat = None
        self._last_check = None
        self._lock = threading.Lock()

    def heartbeat(self):
        with self._lock:
            self._last_beat = self._clock()

    def should_exit(self, active_jobs):
        if active_jobs > 0:
            return False
        with self._lock:
            now = self._clock()
            woke = self._last_check is not None and now - self._last_check > self._wake_gap
            self._last_check = now
            if woke:
                self._last_beat = now
                return False
            if self._last_beat is None:
                return now - self._started > self._grace
            return now - self._last_beat > self._idle_timeout
