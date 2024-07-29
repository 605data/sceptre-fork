"""
this is a hook that just runs the given AWS command with the same AWS_PROFILE
as the current environment settings uses.
"""

from __future__ import absolute_import

import os

from sceptre.hooks import Hook

from devops import (
    api,
)


class tag_virtual_buckets(Hook):
    def run(self):
        self.logger.info("Running {}".format(__name__))
        stack_tags = self.stack.tags
        user_data = self.stack.raw_config["sceptre_user_data"]
        for name, config in user_data["private_buckets"].items():
            if not config.get("virtual"):
                self.logger.debug(
                    (
                        "skipping `{}`, `virtual` is not set and "
                        "this bucket can be tagged normally"
                    ).format(name)
                )
                continue
            tags = stack_tags.copy()
            tags.update(config.get("tags", {}))
            # trigger value.resolve() if this is a deferred result from sceptre
            for k, v in tags.items():
                tags[k] = str(v)
            self.logger.info(
                "{}: tagging {} with {}".format(__name__, name, tags))
            api.bucket_tag_add(env=os.environ["env"], bucket=name, tags=tags)
