import unittest
from queue import Queue
import threading

from sidecar.audio_playback import AudioChunk, play_queued_audio, write_audio_blocks
from sidecar.playback_session import PlaybackSessionController


class FakeStream:
    def __init__(self):
        self.blocks = []

    def write(self, block):
        self.blocks.append(list(block))


class FakePersistentStream(FakeStream):
    def __init__(self, after_write=None):
        super().__init__()
        self.active = False
        self.start_count = 0
        self.stop_count = 0
        self.after_write = after_write

    def start(self):
        self.active = True
        self.start_count += 1

    def stop(self):
        self.active = False
        self.stop_count += 1

    def write(self, block):
        super().write(block)
        if self.after_write is not None:
            self.after_write(self)


class AudioPlaybackTests(unittest.TestCase):
    def test_writes_all_blocks_and_reports_completion(self):
        stream = FakeStream()

        result = write_audio_blocks(
            stream,
            list(range(10)),
            start_offset=0,
            block_size=4,
            should_interrupt=lambda: False,
        )

        self.assertTrue(result.completed)
        self.assertEqual(result.next_offset, 10)
        self.assertEqual(stream.blocks, [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]])

    def test_resume_starts_at_first_unwritten_sample(self):
        stream = FakeStream()

        paused = write_audio_blocks(
            stream,
            list(range(12)),
            start_offset=0,
            block_size=4,
            should_interrupt=lambda: len(stream.blocks) == 2,
        )
        resumed = write_audio_blocks(
            stream,
            list(range(12)),
            start_offset=paused.next_offset,
            block_size=4,
            should_interrupt=lambda: False,
        )

        self.assertFalse(paused.completed)
        self.assertEqual(paused.next_offset, 8)
        self.assertTrue(resumed.completed)
        self.assertEqual(resumed.next_offset, 12)
        self.assertEqual(
            [sample for block in stream.blocks for sample in block],
            list(range(12)),
        )

    def test_calls_before_write_with_exact_ranges(self):
        ranges = []
        successful_ranges = []

        write_audio_blocks(
            FakeStream(),
            list(range(5)),
            start_offset=2,
            block_size=2,
            should_interrupt=lambda: False,
            before_write=lambda start, end: ranges.append((start, end)),
            after_write=lambda start, end: successful_ranges.append((start, end)),
        )

        self.assertEqual(ranges, [(2, 4), (4, 5)])
        self.assertEqual(successful_ranges, [(2, 4), (4, 5)])

    def test_does_not_report_a_failed_write_as_successful(self):
        successful_ranges = []

        class FailingStream:
            def write(self, block):
                raise RuntimeError("device disconnected")

        with self.assertRaises(RuntimeError):
            write_audio_blocks(
                FailingStream(),
                [1, 2],
                start_offset=0,
                block_size=2,
                should_interrupt=lambda: False,
                after_write=lambda start, end: successful_ranges.append((start, end)),
            )

        self.assertEqual(successful_ranges, [])

    def test_rejects_invalid_offsets_and_block_sizes(self):
        with self.assertRaises(ValueError):
            write_audio_blocks(
                FakeStream(),
                [1, 2],
                start_offset=-1,
                block_size=1,
                should_interrupt=lambda: False,
            )
        with self.assertRaises(ValueError):
            write_audio_blocks(
                FakeStream(),
                [1, 2],
                start_offset=0,
                block_size=0,
                should_interrupt=lambda: False,
            )

    def test_queue_player_preserves_multi_chunk_order(self):
        audio_queue = Queue()
        audio_queue.put(AudioChunk(0, [0, 1, 2], 0, "segment-0"))
        audio_queue.put(AudioChunk(1, [3, 4, 5], 0, "segment-1"))
        audio_queue.put(None)
        session = PlaybackSessionController().begin("request")
        first_writes = []
        stream = FakePersistentStream()

        result = play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=2,
            on_first_write=lambda chunk: first_writes.append(chunk.index),
        )

        self.assertFalse(result.cancelled)
        self.assertEqual(result.completed_chunks, 2)
        self.assertEqual(
            [sample for block in stream.blocks for sample in block],
            [0, 1, 2, 3, 4, 5],
        )
        self.assertEqual(first_writes, [0])
        self.assertEqual(session.position().sample_offset, 0)

    def test_queue_player_pauses_and_resumes_at_exact_unwritten_sample(self):
        audio_queue = Queue()
        audio_queue.put(AudioChunk(0, list(range(12)), 0, "segment-0"))
        audio_queue.put(None)
        session = PlaybackSessionController().begin("request")
        paused_positions = []
        resumed_positions = []

        def pause_after_two_blocks(stream):
            if len(stream.blocks) == 2:
                session.pause()

        stream = FakePersistentStream(after_write=pause_after_two_blocks)

        def resume_after_ack(position):
            paused_positions.append(position.sample_offset)
            session.resume()

        result = play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=4,
            on_paused=resume_after_ack,
            on_resumed=lambda position: resumed_positions.append(position.sample_offset),
        )

        self.assertFalse(result.cancelled)
        self.assertEqual(paused_positions, [8])
        self.assertEqual(resumed_positions, [8])
        self.assertEqual(
            [sample for block in stream.blocks for sample in block],
            list(range(12)),
        )

    def test_queue_player_smooths_pause_and_resume_boundaries(self):
        audio_queue = Queue()
        audio_queue.put(AudioChunk(0, [0.8, 0.6, -0.5, -0.7], 0, "segment-0"))
        audio_queue.put(None)
        session = PlaybackSessionController().begin("smooth-request")

        def pause_after_first_block(stream):
            if len(stream.blocks) == 1:
                session.pause()

        stream = FakePersistentStream(after_write=pause_after_first_block)

        def resume_after_ack(_position):
            session.resume()

        play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=2,
            on_paused=resume_after_ack,
            pause_fade_audio=lambda last_sample: [last_sample, last_sample / 2, 0.0],
            fade_in_audio=lambda block: [0.0, block[-1]],
        )

        self.assertEqual(stream.stop_count, 1)
        self.assertEqual(stream.start_count, 2)
        self.assertEqual(stream.blocks, [
            [0.8, 0.6],
            [0.6, 0.3, 0.0],
            [0.0, -0.7],
        ])

    def test_queue_player_cancels_without_writing_future_chunks(self):
        audio_queue = Queue()
        audio_queue.put(AudioChunk(0, list(range(8)), 0, "segment-0"))
        audio_queue.put(AudioChunk(1, list(range(8, 16)), 0, "segment-1"))
        audio_queue.put(None)
        session = PlaybackSessionController().begin("request")

        def cancel_after_first_block(stream):
            if len(stream.blocks) == 1:
                session.cancel()

        stream = FakePersistentStream(after_write=cancel_after_first_block)
        result = play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=4,
        )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.completed_chunks, 0)
        self.assertEqual(stream.blocks, [[0, 1, 2, 3]])

    def test_bounded_queue_drains_a_long_ordered_session_without_deadlock(self):
        audio_queue = Queue(maxsize=3)
        session = PlaybackSessionController().begin("long-request")
        chunk_count = 500

        def produce():
            for index in range(chunk_count):
                audio_queue.put(AudioChunk(index, [index], 0, f"segment-{index}"))
            audio_queue.put(None)

        producer = threading.Thread(target=produce)
        producer.start()
        stream = FakePersistentStream()
        result = play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=1,
        )
        producer.join(timeout=1)

        self.assertFalse(producer.is_alive())
        self.assertEqual(result.completed_chunks, chunk_count)
        self.assertEqual([block[0] for block in stream.blocks], list(range(chunk_count)))
        self.assertEqual(audio_queue.qsize(), 0)

    def test_queue_player_streams_processed_blocks_and_flushes_tail(self):
        audio_queue = Queue()
        audio_queue.put(AudioChunk(0, list(range(6)), 0, "segment-0"))
        audio_queue.put(None)
        session = PlaybackSessionController().begin("processed-request")
        stream = FakePersistentStream()
        processed_inputs = []

        def process(block):
            values = list(block)
            processed_inputs.append(values)
            return [value for value in values for _ in range(2)]

        result = play_queued_audio(
            stream,
            audio_queue,
            session,
            prepare_audio=lambda chunk: chunk.audio,
            block_size=4,
            process_audio_block=process,
            flush_audio=lambda: [99, 100],
            source_block_size=2,
        )

        self.assertEqual(processed_inputs, [[0, 1], [2, 3], [4, 5]])
        self.assertEqual(
            [sample for block in stream.blocks for sample in block],
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 99, 100],
        )
        self.assertEqual(result.completed_chunks, 1)
        self.assertFalse(result.cancelled)


if __name__ == "__main__":
    unittest.main()
