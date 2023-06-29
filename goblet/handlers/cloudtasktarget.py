from goblet.handlers.handler import Handler

import logging
import os

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class CloudTaskTarget(Handler):
    """CloudTask Target"""

    resource_type = "cloudtask_http_target"
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]

    def register(self, name, func, kwargs):
        """
        @app.cloudtasktarget(name="target")
        def my_handler(request):
            pass

        self.resources["target"] = {
            "func": <function my_handler at 0x...>
        }
        """
        if name in self.resources.keys():
            raise Exception(f"cloudtasktarget {name} already registered")

        self.resources[name] = {
            "func": func,
        }

    def __call__(self, request, context=None):
        target = request.headers.get("X-Goblet-CloudTask-Target", None)
        if not target:
            raise ValueError("No X-Goblet-CloudTask-Target header found")

        try:
            return self.resources[target]["func"](request)
        except KeyError:
            log.info(f"{target} not found")
        except Exception as e:
            raise e

    def _deploy(self, source=None, entrypoint=None, config={}):
        self.service_accounts = self.config.cloudtask.get("serviceAccount", [])
        return

    def destroy(self):
        return
