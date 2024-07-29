"""
this is a hook that just runs the given kubectl command with a suitable
kube config for the current (eks) stack.  this is useful for prototyping,
but for permanent stuff you probably want to use ansible-based cluster config

Example usage:
    - !kubectl ...
"""

from __future__ import absolute_import
import os
import re
import six
from helm import EksHook
from devops import util
from devops.api.ecr import ecr_login

LOGGER = util.get_logger("hooks." + __name__)


class kubectl(EksHook):
    def run(self):
        """api interface, this is overriden from parent"""
        error = self.invoke_kubectl(self.argument)
        if error:
            raise SystemExit(error)
