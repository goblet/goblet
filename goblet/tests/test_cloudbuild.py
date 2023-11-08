from goblet import Goblet
from goblet.backends import CloudRun


class TestCloudBuild:
    """
    Test CloudBuild functions
    """

    def cloudbuild_steps(self, config={}, images=["registry:latest"]):
        app = Goblet(config=config)
        cloudrun = CloudRun(app)
        steps = cloudrun._get_cloudbuild_steps(images=images)
        return steps

    def test_cloudbuild_steps_default_cache(self):
        images = ["registry:latest", "registry:tag1", "registry:tag2"]
        steps1 = self.cloudbuild_steps(
            config={"deploy": {"cloudbuild_cache": "DOCKER_LATEST"}}, images=images
        )
        steps2 = self.cloudbuild_steps(images=images)
        assert steps2 == steps1

    def test_cloudbuild_steps_docker_cache_single_tag(self):
        steps = self.cloudbuild_steps(
            config={"deploy": {"cloudbuild_cache": "DOCKER_LATEST"}}
        )
        assert steps[0]["name"] == "gcr.io/cloud-builders/docker"
        assert steps[0]["args"][1] == "docker pull registry:latest || exit 0"
        assert steps[1]["name"] == "gcr.io/cloud-builders/docker"
        assert ["-t", "registry:latest"] in steps[1]["args"]
        assert "--cache-from" in steps[1]["args"]
        assert (
            steps[1]["args"][steps[1]["args"].index("--cache-from") + 1]
            == "registry:latest"
        )

    def test_cloudbuild_steps_docker_cache_multiple_tags(self):
        images = ["registry:latest", "registry:tag1", "registry:tag2"]
        steps = self.cloudbuild_steps(
            config={"deploy": {"cloudbuild_cache": "DOCKER_LATEST"}}, images=images
        )
        assert ["-t", "registry:tag1"] in steps[1]["args"]
        assert ["-t", "registry:tag2"] in steps[1]["args"]

    def test_cloudbuild_steps_kaniko_cache_single_tag(self):
        steps = self.cloudbuild_steps(config={"deploy": {"cloudbuild_cache": "KANIKO"}})
        assert steps[0]["name"] == "gcr.io/kaniko-project/executor:latest"
        assert "--destination=registry:latest" in steps[0]["args"][0]
        assert steps[1]["name"] == "gcr.io/cloud-builders/docker"
        assert steps[1]["args"][1] == "docker pull registry:latest"

    def test_cloudbuild_steps_kaniko_cache_multiple_tags(self):
        images = ["registry:latest", "registry:tag1", "registry:tag2"]
        steps = self.cloudbuild_steps(
            config={"deploy": {"cloudbuild_cache": "KANIKO"}}, images=images
        )
        assert (
            steps[1]["args"][1]
            == "docker pull registry:latest "
            + "&& docker tag registry:latest registry:tag1 "
            + "&& docker tag registry:latest registry:tag2"
        )

    def test_docker_build_args(self, monkeypatch):
        monkeypatch.setenv("GOBLET_BUILD_ARGS", "BUILD_ARG01=arg01,BUILD_ARG02=arg02")
        steps = self.cloudbuild_steps(
            config={"deploy": {"cloudbuild_cache": "DOCKER_LATEST"}}
        )
        assert ["--build-arg", "BUILD_ARG01=arg01"] in steps[1]["args"]
        assert ["--build-arg", "BUILD_ARG02=arg02"] in steps[1]["args"]

    def test_docker_build_args_kaniko_cache(self, monkeypatch):
        monkeypatch.setenv("GOBLET_BUILD_ARGS", "BUILD_ARG01=arg01,BUILD_ARG02=arg02")
        steps = self.cloudbuild_steps(config={"deploy": {"cloudbuild_cache": "KANIKO"}})
        assert ["--build-arg", "BUILD_ARG01=arg01"] in steps[0]["args"]
        assert ["--build-arg", "BUILD_ARG02=arg02"] in steps[0]["args"]
