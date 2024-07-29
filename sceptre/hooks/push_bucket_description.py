"""
This is a hook that puts bucket description to the bucket's README.md file
"""

from __future__ import absolute_import
from multiprocessing.pool import ThreadPool

from sceptre.hooks import Hook

from devops import (
    util,
)

LOGGER = util.get_logger(__name__)


class push_bucket_description(Hook):
    def __init__(self, *args, **kwargs):
        super(push_bucket_description, self).__init__(*args, **kwargs)

    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.
        """
        self.logger.info("Running {}".format(__name__))

        private_buckets = self.stack.raw_config["sceptre_user_data"]["private_buckets"]
        if not private_buckets:
            self.logger.warn("No private buckets configured. Finishing.")
            return
        pool = ThreadPool(10)
        pool.map(self.handle_description_property, private_buckets)
        pool.close()
        pool.join()

    def handle_description_property(self, private_buckets):
        all_buckets = self.stack.raw_config["sceptre_user_data"]["private_buckets"]
        for bucket_name in all_buckets:
            bucket_descr = all_buckets[bucket_name].get("description")
            if bucket_descr:
                msg = "{}:  pushing {}/README.md:\n  {}".format(
                    __name__, bucket_name, bucket_descr
                )
                LOGGER.debug(msg)
                self.stack.connection_manager.call(
                    service="s3",
                    command="put_object",
                    kwargs={
                        "Bucket": bucket_name,
                        "Body": bucket_descr,
                        "Key": "README.md",
                    },
                )
