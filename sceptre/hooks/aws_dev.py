"""
this is a hook that just runs the given AWS command with the same AWS_PROFILE
as the current environment settings uses.
"""

from __future__ import absolute_import
import os
from sceptre.hooks import Hook


class aws_dev(Hook):
    def run(self):
        cmd = "AWS_PROFILE={0} AWS_DEFAULT_REGION={1} aws {2}".format(
            "605-dev", "us-east-1", self.argument
        )
        self.logger.info("running: {0}".format(cmd))
        os.system(cmd)
