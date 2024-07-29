"""
This is a sceptre resolver that pulls data from bash.

This is usually used as a last resort out of sheer desperation,
often to pull things from shell commands so we can push them into
cloudformation stack outputs.

Here's a pretty complicated example that includes sceptre-templating
of the commands from global config, pipes, and backtick substitution:

    !bash_resolver
      echo "arn:aws:kms:{{environment_config.region}}:{{environment_config.account_id}}:key/`AWS_PROFILE={{environment_config.profile}} aws kms list-aliases | jq -r '.Aliases[]|select(.AliasName=="alias/core-ssm").TargetKeyId'`"
"""
from __future__ import absolute_import
import os
import subprocess
from sceptre.resolvers import Resolver

# from devops import (util, )

SCEPTRE_ROOT = os.environ["SCEPTRE_ROOT"]


class bash_resolver(Resolver):
    def __init__(self, *args, **kwargs):
        super(bash_resolver, self).__init__(*args, **kwargs)

    def exec_cmd(self, cmd):
        """chains to bash and returns the result"""
        result = subprocess.check_output(
            ["bash", "-c", cmd], cwd=SCEPTRE_ROOT).strip()
        if isinstance(result, bytes):
            return result.decode("utf-8")
        else:
            return result

    def resolve(self):
        """main entry point, overridden from Resolver class"""
        msg = "{}: \n  {}".format(
            self.__class__.__name__, self.argument).strip()
        self.logger.info(msg.strip())
        tmp = self.exec_cmd(self.argument)
        self.logger.info("  {}{}".format((" ⇢  "), tmp))
        return tmp
