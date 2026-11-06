import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

Pin = TypeVar("Pin")


class DemoCapacityError(Exception):
    """Raised when adding a pin would exceed the store's active-pin limit."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DemoPinStore(Generic[Pin]):
    """In-memory holder for temporary demo pins, with a lifetime and a cap.

    Pins expire lazily: expired ones are dropped whenever the store is read or
    written, so no background task has to wake up and delete them. The clock is
    injectable so tests can move time forward instead of sleeping.

    Routes using the store run on FastAPI's thread pool, so two requests can
    call add() at the same moment. The lock makes "check the cap, then insert"
    one atomic step; without it both could see 4 pins and both insert.
    """

    def __init__(
        self,
        max_active: int = 5,
        ttl: timedelta = timedelta(seconds=60),
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._max_active = max_active
        self._ttl = ttl
        self._clock = clock
        self._pins: dict[str, tuple[Pin, datetime]] = {}  # id → (pin, expires_at)
        self._lock = threading.Lock()

    @property
    def ttl_seconds(self) -> int:
        """How long a pin stays visible after it is added."""
        return int(self._ttl.total_seconds())

    def is_full(self) -> bool:
        """True if no more pins can be added right now."""
        with self._lock:
            self._drop_expired()
            return len(self._pins) >= self._max_active

    def add(self, pin_id: str, pin: Pin) -> None:
        """Store a pin until its lifetime ends. Raises DemoCapacityError if full."""
        with self._lock:
            self._drop_expired()
            if len(self._pins) >= self._max_active:
                raise DemoCapacityError(f"{self._max_active} demo pins are already active")
            self._pins[pin_id] = (pin, self._clock() + self._ttl)

    def active(self) -> list[Pin]:
        """Pins that haven't expired, oldest first."""
        with self._lock:
            self._drop_expired()
            return [pin for pin, _ in self._pins.values()]

    def remove(self, pin_id: str) -> bool:
        """Remove one pin. Returns False if no active pin has that ID."""
        with self._lock:
            self._drop_expired()
            return self._pins.pop(pin_id, None) is not None

    def clear(self) -> None:
        """Remove every pin."""
        with self._lock:
            self._pins.clear()

    def _drop_expired(self) -> None:
        # Callers must hold self._lock.
        now = self._clock()
        self._pins = {pid: entry for pid, entry in self._pins.items() if entry[1] > now}
