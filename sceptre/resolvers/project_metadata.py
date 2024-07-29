"""
"""
from __future__ import absolute_import
import os
import subprocess
from sceptre.resolvers import Resolver

SCEPTRE_ROOT = os.environ["SCEPTRE_ROOT"]


class project_metadata(Resolver):
    def __init__(self, *args, **kwargs):
        super(project_metadata, self).__init__(*args, **kwargs)

    def exec_cmd(self, cmd):
        result = subprocess.check_output(cmd.split(), cwd=SCEPTRE_ROOT).strip()
        if isinstance(result, bytes):
            return result.decode("utf-8")
        else:
            return result

    def resolve(self):
        """ """
        # self.logger.debug('resolving project metadata')
        if self.argument == "__file__":
            return os.path.join(
                SCEPTRE_ROOT, "config", os.environ["env"], os.environ["stack"] + ".yaml"
            )
        if self.argument == "__repo__":
            # something like git@github.com:605data/stack-core.git
            remote = self.exec_cmd("git config --get remote.origin.url")
            return os.path.splitext(os.path.basename(remote))[0]
        if self.argument == "__sha__":
            return self.exec_cmd("git rev-parse HEAD")
        if self.argument == "__stack_name__":
            return "!Ref AWS::StackName"
        raise ValueError("unsupported argument: {0}".format(self.argument))
