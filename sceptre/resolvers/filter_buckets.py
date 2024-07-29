""" filter_buckets_by_tag
"""
from __future__ import absolute_import
from sceptre.resolvers.stack_output import Resolver
from devops import api, util

LOGGER = util.get_logger(__name__)


class FilterBuckets(Resolver):
    """Returns all exports for a given stack
    Usage:
        # get buckets by environment that have the given tag
        !filter_buckets env=legacy, tag=DevReadOnly

        # get buckets by environment that have the given tag value
        !filter_buckets env=legacy, tag=DevReadOnly, value=...
    """

    def resolve(self):
        """main method for resolver"""
        tmp = self.argument.split(",")
        tmp = [arg.split("=") for arg in tmp]
        tmp = [[x.strip() for x in arg] for arg in tmp]
        try:
            kwargs = dict(tmp)
        except ValueError:
            LOGGER.critical("error converting to dict: {}".format(tmp))
            raise
        LOGGER.debug("dispatching with {}".format(kwargs))
        result = api.bucket_tags(**kwargs)
        LOGGER.debug("resolved: {}".format(result))
        if not result:
            err = (
                "filter after {} is empty, "
                "crashing because this is probably not what you wanted"
            )
            err = err.format(kwargs)
            LOGGER.critical(err)
            raise RuntimeError(err)

        return result


class AllBuckets(FilterBuckets):
    """
    Returns names (not arns) for all buckets in the current environment
    Example usage:
        - !all_buckets
    """

    def resolve(self):
        resp = self.stack.connection_manager.call(
            service="s3", command="list_buckets")
        return [x["Name"] for x in resp["Buckets"]]
