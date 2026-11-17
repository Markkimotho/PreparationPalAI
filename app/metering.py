"""Per-request model usage collection. A no-op unless a metering scope is open.

The billing layer opens a scope around each model-backed action; every model call
made inside records one `UsageRecord`. Context variables travel into worker threads
started with anyio/Starlette thread pools, so records made there land in the same meter.
"""
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

Purpose = Literal['main', 'guard', 'vision', 'embed']


@dataclass(frozen=True)
class UsageRecord:
    alias: str
    purpose: Purpose
    input_tokens: int
    output_tokens: int
    estimated: bool = False


@dataclass
class Meter:
    action: str
    request_id: str
    on_add: Callable[[UsageRecord], None] | None = None
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, usage: UsageRecord) -> None:
        # Keep the record first: the call that crosses a limit must still be charged.
        self.records.append(usage)
        if self.on_add:
            self.on_add(usage)


_meter: ContextVar[Meter | None] = ContextVar('usage_meter', default=None)


@contextmanager
def metering_scope(action: str, request_id: str, on_add: Callable[[UsageRecord], None] | None = None):
    if _meter.get() is not None:
        raise RuntimeError('A metering scope is already open for this request')
    meter = Meter(action, request_id, on_add)
    token = _meter.set(meter)
    try:
        yield meter
    finally:
        _meter.reset(token)


def current_meter() -> Meter | None:
    return _meter.get()


def current_action() -> tuple[str, str] | None:
    meter = _meter.get()
    return (meter.action, meter.request_id) if meter else None


def record(usage: UsageRecord) -> None:
    meter = _meter.get()
    if meter is not None:
        meter.add(usage)
