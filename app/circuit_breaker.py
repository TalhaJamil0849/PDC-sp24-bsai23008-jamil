import time
import threading
from enum import Enum


class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    A simple thread-safe Circuit Breaker.

    States:
        CLOSED    - normal operation, requests pass through
        OPEN      - too many failures, requests are blocked immediately
        HALF_OPEN - cooldown passed, one probe request is allowed through
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self._state = State.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        with self._lock:
            if self._state == State.OPEN:
                if time.time() - self._opened_at >= self.cooldown_seconds:
                    self._state = State.HALF_OPEN
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = State.CLOSED
            self._opened_at = None

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = State.OPEN
                self._opened_at = time.time()

    def is_open(self) -> bool:
        return self.state == State.OPEN

    def allow_request(self) -> bool:
        """Returns True if the request should be allowed through."""
        s = self.state
        if s == State.CLOSED:
            return True
        if s == State.HALF_OPEN:
            return True
        return False  # OPEN
