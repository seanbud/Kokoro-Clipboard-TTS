"""Small, deterministic audio-write primitives used by the sidecar.

This module intentionally has no sounddevice or model imports. Tests can use a
fake stream to verify exact offsets, interruption behavior, and event timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty
from typing import Any, Callable


@dataclass(frozen=True)
class BlockWriteResult:
    next_offset: int
    completed: bool


@dataclass(frozen=True)
class AudioChunk:
    index: int
    audio: Any
    pause_after_ms: int
    segment_id: str


@dataclass(frozen=True)
class QueuePlaybackResult:
    completed_chunks: int
    cancelled: bool


def write_audio_blocks(
    stream: Any,
    audio: Any,
    *,
    start_offset: int,
    block_size: int,
    should_interrupt: Callable[[], bool],
    before_write: Callable[[int, int], None] | None = None,
    after_write: Callable[[int, int], None] | None = None,
) -> BlockWriteResult:
    """Write audio sequentially and return the first unwritten sample offset.

    The offset advances only after ``stream.write`` succeeds. A caller can retain
    ``next_offset`` across pause/resume without replaying completed blocks.
    """

    if block_size <= 0:
        raise ValueError("block_size must be positive")
    if start_offset < 0 or start_offset > len(audio):
        raise ValueError("start_offset is outside the audio buffer")

    offset = start_offset
    while offset < len(audio):
        if should_interrupt():
            return BlockWriteResult(next_offset=offset, completed=False)

        end_offset = min(offset + block_size, len(audio))
        if before_write is not None:
            before_write(offset, end_offset)
        start_offset_for_write = offset
        stream.write(audio[offset:end_offset])
        offset = end_offset
        if after_write is not None:
            after_write(start_offset_for_write, end_offset)

    return BlockWriteResult(next_offset=offset, completed=True)


def play_queued_audio(
    stream: Any,
    audio_queue: Any,
    session: Any,
    *,
    prepare_audio: Callable[[AudioChunk], Any],
    block_size: int,
    on_first_write: Callable[[AudioChunk], None] | None = None,
    on_paused: Callable[[Any], None] | None = None,
    on_resumed: Callable[[Any], None] | None = None,
    process_audio_block: Callable[[Any], Any] | None = None,
    flush_audio: Callable[[], Any] | None = None,
    source_block_size: int = 480,
    queue_timeout: float = 0.05,
) -> QueuePlaybackResult:
    """Consume ``AudioChunk`` items until a ``None`` sentinel or cancellation.

    This is the production playback state machine, with model and sounddevice
    details injected by the caller so deterministic fake-stream tests exercise
    the same chunk ordering and exact-offset pause/resume behavior as the app.
    """
    if queue_timeout <= 0:
        raise ValueError("queue_timeout must be positive")
    if process_audio_block is not None and source_block_size <= 0:
        raise ValueError("source_block_size must be positive")

    current_chunk = None
    current_audio = None
    current_offset = 0
    pending_audio = None
    pending_offset = 0
    end_received = False
    completed_chunks = 0
    playback_started = False
    stream.start()

    while not session.cancel_event.is_set():
        if session.pause_event.is_set():
            stream.stop()
            if session.acknowledge_pause() and on_paused is not None:
                on_paused(session.position())
            session.cancel_event.wait(0.01)
            continue

        if not stream.active:
            stream.start()
            if session.acknowledge_resume() and on_resumed is not None:
                on_resumed(session.position())

        def after_write(start_offset: int, end_offset: int) -> None:
            nonlocal playback_started
            if not playback_started and current_chunk is not None:
                if on_first_write is not None:
                    on_first_write(current_chunk)
                playback_started = True

        if pending_audio is not None:
            result = write_audio_blocks(
                stream,
                pending_audio,
                start_offset=pending_offset,
                block_size=block_size,
                should_interrupt=lambda: (
                    session.cancel_event.is_set() or session.pause_event.is_set()
                ),
                after_write=after_write,
            )
            pending_offset = result.next_offset
            if not result.completed:
                if session.pause_event.is_set():
                    stream.stop()
                    if session.acknowledge_pause() and on_paused is not None:
                        on_paused(session.position())
                continue
            pending_audio = None
            pending_offset = 0
            continue

        if end_received:
            break

        if current_chunk is None:
            try:
                current_chunk = audio_queue.get(timeout=queue_timeout)
            except Empty:
                continue
            if current_chunk is None:
                end_received = True
                if flush_audio is not None:
                    flushed_audio = flush_audio()
                    if len(flushed_audio) > 0:
                        pending_audio = flushed_audio
                continue

        if current_audio is None:
            current_audio = prepare_audio(current_chunk)
            current_offset = 0
            session.set_position(current_chunk.index, current_offset)

        if process_audio_block is not None:
            if current_offset < len(current_audio):
                end_offset = min(current_offset + source_block_size, len(current_audio))
                pending_audio = process_audio_block(
                    current_audio[current_offset:end_offset]
                )
                current_offset = end_offset
                session.set_position(current_chunk.index, current_offset)
                if len(pending_audio) == 0:
                    pending_audio = None
                continue

            audio_queue.task_done()
            completed_chunks += 1
            current_chunk = None
            current_audio = None
            current_offset = 0
            session.clear_position()
            continue

        result = write_audio_blocks(
            stream,
            current_audio,
            start_offset=current_offset,
            block_size=block_size,
            should_interrupt=lambda: (
                session.cancel_event.is_set() or session.pause_event.is_set()
            ),
            after_write=after_write,
        )
        current_offset = result.next_offset
        session.set_position(current_chunk.index, current_offset)

        if not result.completed:
            if session.pause_event.is_set():
                stream.stop()
                if session.acknowledge_pause() and on_paused is not None:
                    on_paused(session.position())
            continue

        audio_queue.task_done()
        completed_chunks += 1
        current_chunk = None
        current_audio = None
        current_offset = 0
        session.clear_position()

    return QueuePlaybackResult(
        completed_chunks=completed_chunks,
        cancelled=session.cancel_event.is_set(),
    )
