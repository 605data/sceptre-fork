"""
This is a hook that puts bucket description to the bucket's README.md file
"""

from __future__ import absolute_import

import os
from multiprocessing.pool import ThreadPool

from sceptre.hooks import Hook

from devops import (
    util,
)

LOGGER = util.get_logger(__name__)


class bash(Hook):
    def __init__(self, *args, **kwargs):
        super(bash, self).__init__(*args, **kwargs)
        # self.stack_aws_profile = self.stack_group_config['profile']

    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)

        The following attributes may be available from the base class:
        self.stack_config  (A dict of data from <stack_name>.yaml)
        self.stack_group_config  (A dict of data from config.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        tmp = self.argument.strip()
        self.logger.info("{}".format(tmp))
        error = os.system(tmp)
        if error:
            raise RuntimeError(tmp)
