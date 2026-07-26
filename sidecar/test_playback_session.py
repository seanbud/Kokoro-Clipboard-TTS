import threading
import unittest

try:
    from .playback_session import PlaybackSessionController
except ImportError:
    from playback_session import PlaybackSessionController


class PlaybackSessionControllerTests(unittest.TestCase):
    def test_new_session_cancels_only_the_previous_session(self):
        controller = PlaybackSessionController()
        previous = controller.begin("previous")
        current = controller.begin("current")

        self.assertTrue(previous.cancel_event.is_set())
        self.assertFalse(current.cancel_event.is_set())
        self.assertIs(controller.active(), current)

    def test_stale_clear_cannot_remove_current_session(self):
        controller = PlaybackSessionController()
        stale = controller.begin("stale")
        current = controller.begin("current")

        controller.clear(stale)

        self.assertIs(controller.active(), current)

    def test_controls_and_position_are_owned_by_one_session(self):
        controller = PlaybackSessionController()
        session = controller.begin("request")

        session.set_position(chunk_index=3, sample_offset=4812)
        session.pause()
        self.assertTrue(session.pause_event.is_set())
        self.assertTrue(session.acknowledge_pause())
        self.assertFalse(session.acknowledge_pause())
        self.assertEqual(session.position().chunk_index, 3)
        self.assertEqual(session.position().sample_offset, 4812)

        session.resume()
        self.assertFalse(session.pause_event.is_set())
        self.assertTrue(session.acknowledge_resume())
        self.assertFalse(session.acknowledge_resume())
        session.clear_position()
        self.assertIsNone(session.position().chunk_index)
        self.assertEqual(session.position().sample_offset, 0)

    def test_stale_and_missing_control_ids_are_rejected(self):
        controller = PlaybackSessionController()
        _, error = controller.control_target("missing")
        self.assertEqual(error, "no_active_session")

        current = controller.begin("current")
        target, error = controller.control_target("stale")
        self.assertIsNone(target)
        self.assertEqual(error, "stale_session")
        self.assertIs(controller.control_target("current")[0], current)

    def test_speed_versions_are_acknowledged_once(self):
        session = PlaybackSessionController().begin("request", initial_speed=1.2)
        speed, version = session.speed_snapshot()
        self.assertEqual(speed, 1.2)
        self.assertEqual(version, 1)
        self.assertTrue(session.acknowledge_speed(version))
        self.assertFalse(session.acknowledge_speed(version))

        next_version = session.set_speed(1.8)
        self.assertGreater(next_version, version)
        self.assertEqual(session.speed_snapshot(), (1.8, next_version))
        with self.assertRaises(ValueError):
            session.set_speed(2.1)

    def test_concurrent_replacements_leave_one_uncancelled_session(self):
        controller = PlaybackSessionController()
        sessions = []
        sessions_lock = threading.Lock()

        def replace(index):
            session = controller.begin(f"request-{index}")
            with sessions_lock:
                sessions.append(session)

        threads = [threading.Thread(target=replace, args=(index,)) for index in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        active = controller.active()
        self.assertIsNotNone(active)
        self.assertEqual(sum(not session.cancel_event.is_set() for session in sessions), 1)
        self.assertIs(next(session for session in sessions if not session.cancel_event.is_set()), active)


if __name__ == "__main__":
    unittest.main()
