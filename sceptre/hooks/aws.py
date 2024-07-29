"""
this is a hook that just runs the given AWS command with the same AWS_PROFILE
as the current environment settings uses.

Example usage:
    # parametric invocation, explicit and possibly external env
    - !aws 605-dev@us-east-1 sts get-caller-identity

    # parametric version, the current environment
    - !aws {{environment_config.profile}}@{{environment_config.region}} sts get-caller-identity

    # same as above, using the implied current environment
    - !aws sts get-caller-identity
"""

from __future__ import absolute_import
import os
from sceptre.hooks import Hook


class aws(Hook):
    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)

        The following attributes may be available from the base class:
        self.stack.raw_config  (A dict of data from <stack_name>.yaml)
        self.environment_config  (A dict of data from config.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        args = self.argument.strip().split()
        context, args = args[0], args[1:]
        self.logger.debug("command context: {}".format(context))
        try:
            profile, region = context.split("@")
        except ValueError:
            msg = "could not parse command context `{}` " 'as "profile@region"'
            self.logger.warning(msg.format(context))
            profile, region = (self.stack.profile, self.stack.region)
            msg = "defaults from environment config will be used: {}@{}"
            self.logger.warning(msg.format(profile, region))
            args = [context] + args
        args = " ".join(args)
        cmd = "AWS_PROFILE={0} AWS_DEFAULT_REGION={1} aws {2}".format(
            profile, region, args
        )
        self.logger.info("running: {0}".format(cmd))
        os.system(cmd)
