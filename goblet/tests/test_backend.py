from goblet import Goblet
from goblet.backends.backend import Backend


class TestBackend:
    def test_custom_files(self):
        test_custom_files = {
            "custom_files": {"include": ["*.yaml"], "exclude": [".secret"]}
        }
        backend = Backend(Goblet(), None, None, config=test_custom_files)

        assert "*.yaml" in backend.zip_config["include"]
        assert "*.py" in backend.zip_config["include"]
        assert ".secret" in backend.zip_config["exclude"]
        assert "build" in backend.zip_config["exclude"]
