import unittest
from unittest.mock import patch

try:
    from . import kokoro_server
except ImportError:
    import kokoro_server


class FakeModel:
    def __init__(self, **_kwargs):
        self.training = True

    def eval(self):
        self.training = False
        return self


class PipelineInitializationTests(unittest.TestCase):
    def tearDown(self):
        kokoro_server.pipeline = None

    def test_preloaded_offline_model_uses_evaluation_mode(self):
        created = {}

        def fake_pipeline(*, model, **_kwargs):
            created["model"] = model
            return object()

        kokoro_server.pipeline = None
        with (
            patch.object(kokoro_server, "KModel", FakeModel),
            patch.object(kokoro_server, "KPipeline", side_effect=fake_pipeline),
        ):
            kokoro_server.get_pipeline()

        self.assertFalse(created["model"].training)


if __name__ == "__main__":
    unittest.main()
