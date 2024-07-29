"""
this is a hook that just runs the given helm command with a suitable
kube config for the current (eks) stack. this is useful for prototyping,
but for permanent stuff you probably want to use ansible-based cluster config

Example usage:
    - !helm ...
"""

from __future__ import absolute_import
from eks_hooks import EksHook
import os
from devops import util
from devops.api.ecr import ecr_login

LOGGER = util.get_logger("hooks." + __name__)


class helm(EksHook):
    def run(self):
        """api interface, this is overriden from parent"""
        cmd = self.argument
        if cmd == "init":
            # during initialization be sure that helm can auth afterwards
            self.init_kubeconfig()
        else:
            error = self.invoke_helm()
            if error:
                raise SystemExit(error)
