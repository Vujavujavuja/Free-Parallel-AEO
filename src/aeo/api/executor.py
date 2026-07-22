"""In-process run executor + progress broker (PRD §6.1 RunExecutor).

Runs execute as background asyncio tasks in the FastAPI event loop. Each
progress event is buffered per run and fanned out to any SSE subscribers, so a
client that connects late still catches up on the full history.
"""

from __future__ import annotations

import asyncio

from aeo.constants import RunStatus
from aeo.core.pipeline import ProgressEvent
from aeo.schemas.run import RunRecord
from aeo.services import run_service
from aeo.settings import Settings
from aeo.storage import RunStore

_STREAM_CLOSING = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.AWAITING_APPROVAL}


class RunBroker:
    """Buffers progress events per run and fans them out to SSE subscribers."""

    def __init__(self) -> None:
        self._history: dict[str, list[ProgressEvent]] = {}
        self._subscribers: dict[str, set[asyncio.Queue[ProgressEvent]]] = {}
        self._tasks: dict[str, asyncio.Task[RunRecord]] = {}

    async def emit(self, event: ProgressEvent) -> None:
        self._history.setdefault(event.run_id, []).append(event)
        for queue in list(self._subscribers.get(event.run_id, ())):
            queue.put_nowait(event)

    def subscribe(self, run_id: str) -> asyncio.Queue[ProgressEvent]:
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        for event in self._history.get(run_id, []):
            queue.put_nowait(event)
        self._subscribers.setdefault(run_id, set()).add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[ProgressEvent]) -> None:
        subs = self._subscribers.get(run_id)
        if subs:
            subs.discard(queue)

    def is_running(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def _track(self, run_id: str, task: asyncio.Task[RunRecord]) -> None:
        self._tasks[run_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(run_id, None))

    def start(
        self,
        record: RunRecord,
        *,
        provider_name: str,
        settings: Settings,
        store: RunStore,
    ) -> None:
        """Kick off a new run in the background."""

        async def _run() -> RunRecord:
            return await run_service.execute_run(
                record,
                provider_name=provider_name,
                settings=settings,
                store=store,
                emit=self.emit,
                stop_for_approval=True,
            )

        self._track(record.id, asyncio.create_task(_run()))

    def resume(
        self,
        record: RunRecord,
        *,
        provider_name: str,
        settings: Settings,
        store: RunStore,
    ) -> None:
        """Resume a run that was paused for question approval."""

        async def _run() -> RunRecord:
            return await run_service.resume_run(
                record,
                provider_name=provider_name,
                settings=settings,
                store=store,
                emit=self.emit,
            )

        self._track(record.id, asyncio.create_task(_run()))


_broker = RunBroker()


def get_broker() -> RunBroker:
    return _broker


def stream_closes_on(status: RunStatus) -> bool:
    return status in _STREAM_CLOSING
