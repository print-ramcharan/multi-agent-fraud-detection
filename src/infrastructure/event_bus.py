"""
Kafka-compatible in-memory event bus.

Provides an async pub/sub event bus using ``asyncio.Queue`` per topic,
mirroring Kafka's topic-based messaging for local development.

Pre-defined topics:
- transactions.in     – raw incoming transactions
- tier1.results       – Tier-1 agent outputs
- specialist.results  – Specialist agent outputs
- decisions.out       – final decision results
- audit.events        – audit trail events
- alerts.events       – real-time alert notifications
- feedback.raw        – human feedback loop data
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default topics created on bus initialization
DEFAULT_TOPICS: list[str] = [
    "transactions.in",
    "tier1.results",
    "specialist.results",
    "decisions.out",
    "audit.events",
    "alerts.events",
    "feedback.raw",
]


class Event(BaseModel):
    """Envelope for an event published to the bus."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="system", description="Component that published the event")


# Type alias for subscriber callbacks
SubscriberCallback = Callable[[Event], Awaitable[None]]


class InMemoryEventBus:
    """Async, Kafka-like event bus backed by ``asyncio.Queue`` per topic.

    Each topic maintains:
    - A queue for buffering events.
    - A list of subscriber callbacks.
    - A consumer task that drains the queue and fans out to subscribers.
    """

    def __init__(self, maxsize: int = 10_000) -> None:
        """Initialise the event bus.

        Args:
            maxsize: Maximum events buffered per topic queue.
        """
        self._queues: dict[str, asyncio.Queue[Event]] = {}
        self._subscribers: dict[str, list[SubscriberCallback]] = {}
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._maxsize = maxsize
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create default topics and start consumer tasks."""
        for topic in DEFAULT_TOPICS:
            await self.create_topic(topic)
        self._started = True
        logger.info("EventBus started with topics: %s", list(self._queues.keys()))

    async def stop(self) -> None:
        """Cancel all consumer tasks and drain queues."""
        self._started = False
        for task in self._consumer_tasks.values():
            task.cancel()
        for task in self._consumer_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumer_tasks.clear()
        self._queues.clear()
        self._subscribers.clear()
        logger.info("EventBus stopped.")

    # ------------------------------------------------------------------
    # Topic management
    # ------------------------------------------------------------------

    async def create_topic(self, topic: str) -> None:
        """Create a topic if it does not already exist."""
        if topic in self._queues:
            return
        self._queues[topic] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[topic] = []
        self._consumer_tasks[topic] = asyncio.create_task(
            self._consumer_loop(topic)
        )
        logger.debug("Topic created: %s", topic)

    def list_topics(self) -> list[str]:
        """Return all registered topic names."""
        return list(self._queues.keys())

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        source: str = "system",
    ) -> str:
        """Publish a payload to a topic.

        Args:
            topic: Target topic name (auto-created if missing).
            payload: Event payload dict.
            source: Name of the publishing component.

        Returns:
            The generated event ID.
        """
        if topic not in self._queues:
            await self.create_topic(topic)

        event = Event(topic=topic, payload=payload, source=source)
        await self._queues[topic].put(event)
        logger.debug("Published event %s to %s", event.event_id, topic)
        return event.event_id

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    async def subscribe(
        self, topic: str, callback: SubscriberCallback
    ) -> None:
        """Register a callback for a topic.

        Args:
            topic: Topic to subscribe to (auto-created if missing).
            callback: Async callable that receives an ``Event``.
        """
        if topic not in self._queues:
            await self.create_topic(topic)
        self._subscribers[topic].append(callback)
        logger.debug(
            "Subscriber added to %s (total: %d)",
            topic,
            len(self._subscribers[topic]),
        )

    # ------------------------------------------------------------------
    # Internal consumer
    # ------------------------------------------------------------------

    async def _consumer_loop(self, topic: str) -> None:
        """Drain the queue for *topic* and fan out to subscribers."""
        queue = self._queues[topic]
        while True:
            try:
                event = await queue.get()
                subscribers = self._subscribers.get(topic, [])
                for cb in subscribers:
                    try:
                        await cb(event)
                    except Exception:
                        logger.exception(
                            "Subscriber error on topic %s for event %s",
                            topic,
                            event.event_id,
                        )
                queue.task_done()
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    async def drain(self, topic: str, timeout: float = 5.0) -> None:
        """Wait until all queued events on *topic* are processed."""
        if topic in self._queues:
            try:
                await asyncio.wait_for(
                    self._queues[topic].join(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Drain timeout on topic %s", topic)

    def pending_count(self, topic: str) -> int:
        """Return number of unprocessed events in a topic queue."""
        if topic in self._queues:
            return self._queues[topic].qsize()
        return 0
