# -*- coding: utf-8 -*-
""" downstream_stacks.py

This is a hook that updates "downstream" stacks, i.e. stacks
that always require updates after this stack is updated.  This
obviously makes updates much slower, so use it wisely.  This
hook is pretty naive, basically just running the standard `make`
target for sceptre.  Don't expect it to update stacks outside of
the current repo, etc

Example Usage:

```
hooks:
  after_update:
    - !downstream_stack dev/iam-roles
```
"""
from __future__ import absolute_import
from sceptre.hooks import Hook
from devops import (
    util,
)


class downstream_stack(Hook):
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
        env, stack = [x.strip() for x in self.argument.split("/")]
        cmd_t = "env={} stack={} make sceptre-launch-stack"
        cmd = cmd_t.format(env, stack)
        self.logger.info("running: {0}".format(cmd))
        util.invoke(cmd)
