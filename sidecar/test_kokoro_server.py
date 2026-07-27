import unittest

try:
    from .pipeline_loader import create_offline_pipeline
except ImportError:
    from pipeline_loader import create_offline_pipeline


class FakeModel:
    def __init__(self, **_kwargs):
        self.training = True

    def eval(self):
        self.training = False
        return self


class PipelineInitializationTests(unittest.TestCase):
    def test_preloaded_offline_model_uses_evaluation_mode(self):
        created = {}

        def fake_pipeline(*, model, **_kwargs):
            created["model"] = model
            return object()

        create_offline_pipeline(
            FakeModel,
            fake_pipeline,
            repo_id="hexgrad/Kokoro-82M",
            config_path="config.json",
            model_path="kokoro-v1_0.pth",
        )

        self.assertFalse(created["model"].training)


if __name__ == "__main__":
    unittest.main()
