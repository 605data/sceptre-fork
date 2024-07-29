""" stack_exports_filter
"""
from __future__ import absolute_import
from functools import reduce
from sceptre.resolvers.stack_output import Resolver
from devops import (
    util,
)
from devops.environment import Environment

# use our  logger, the formatter is nicer than sceptre
LOGGER = util.get_logger(__name__)


class StackExportFilter(Resolver):
    """Returns all exports for a given stack
    Usage:
        !stack_exports_filter env_name/stack_regex::key_regex
    """

    @property
    def key_regex(self):
        tmp = self.argument.split("::")[-1].replace("\n", " ").strip()
        return tmp.split(" ")[0]

    @property
    def extra_filters(self):
        # everything after the key regex
        tmp = self.argument.split("::")[-1].replace("\n", " ").strip()
        tmp = tmp.split(" ")[1:]
        # convert to key/values
        tmp = dict([x.split("=") for x in tmp])
        return tmp

    @property
    def stack_regex(self):
        """extracts simple stack name from argument"""
        _, tmp = self.argument.split("::")[0].split("/")
        return tmp

    @property
    def env_name(self):
        """extracts env name from argument"""
        tmp, _ = self.argument.split("::")[0].split("/")
        return tmp

    def resolve(self):
        """main method for resolver"""
        LOGGER.info(
            "{}: resolving: {}".format(
                __name__,
                [self.env_name, self.stack_regex,
                    self.key_regex, self.extra_filters],
            )
        )
        env = Environment.from_name(self.env_name)
        # LOGGER.debug('{}: external environment: {}'.format(__name__, env))
        stack_matches = env.stacks.filter(self.stack_regex)
        stack_matches = stack_matches.filter(**self.extra_filters)
        export_matches = stack_matches.exports.filter(self.key_regex)
        export_lists = [list(export_dict.values())
                        for export_dict in export_matches]
        if not export_lists:
            msg = (
                "given stack regex {} and key regex {} "
                "no results survived filter! crashing now "
                "because this is probably not what you expected.."
            )
            msg = msg.format(self.stack_regex, self.key_regex)
            LOGGER.warning(msg)
            raise RuntimeError(msg)
        else:
            results = reduce(lambda x, y: x + y, export_lists)
        LOGGER.info("\t{} resolved: {}".format(__name__, util.blue(results)))
        return results
