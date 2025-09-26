"""Simple publish/subscribe event bus."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from typing import Protocol


class Subscriber(Protocol):
    """Callable protocol for event subscribers."""

    def __call__(self, payload: object) -> Awaitable[None] | None: ...


class EventBus:
    """A lightweight pub/sub message bus for UI coordination."""

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        """Register *callback* for *topic*."""

        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Subscriber) -> None:
        """Remove *callback* from *topic*."""

        callbacks = self._subscribers.get(topic)
        if not callbacks:
            return
        if callback in callbacks:
            callbacks.remove(callback)

    def publish(self, topic: str, payload: object) -> None:
        """Publish *payload* on *topic*."""

        callbacks = list(self._subscribers.get(topic, []))
        for callback in callbacks:
            result = callback(payload)
            if asyncio.iscoroutine(result):
                self._loop.create_task(result)


__all__ = ["EventBus"]
