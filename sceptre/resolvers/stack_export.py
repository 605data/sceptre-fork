from __future__ import absolute_import
from devops import (
    util,
)
import os
import json
import re
import yaml
from six.moves import filter

from sceptre.context import SceptreContext
from sceptre.connection_manager import ConnectionManager
from sceptre.resolvers.stack_output import Resolver

from pygments import highlight, lexers, formatters

PYGMENTS_LEXER = lexers.PythonLexer()
PYGMENTS_FORMATTER = formatters.Terminal256Formatter(style="rrt")


def highlighter(x):
    return highlight(x, PYGMENTS_LEXER, PYGMENTS_FORMATTER)


ENV_CACHE = {}
CM_CACHE = {}
RESULTS_CACHE = {}


def snake(name):
    # FIXME: move to common libs
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return name


class StackExports(Resolver):
    """Returns all exports for a given stack
    usage:
        !stack_exports env_name/stack_name
    """

    env_cache = {}
    cm_cache = {}

    def __init__(self, *args, **kwargs):
        argument = kwargs.pop("argument", None)
        if argument and not argument.endswith("::"):
            argument += "::"
            kwargs["argument"] = argument
        super(StackExports, self).__init__(*args, **kwargs)
        tmp_name = "resolvers."
        tmp_name += os.path.splitext(os.path.basename(__file__))[0]
        tmp_name += "." + snake(__name__)
        self.logger = util.get_logger(tmp_name)
        # quiet output if we're running from atlantis
        if os.environ.get("ATLANTIS_LOG_LEVEL"):
            self.logger.info = lambda *args, **kargs: None

    def resolve(self):
        """main method for resolver"""
        msg = "resolving: {}".format([self.env_name, self.stack_name]).strip()
        msg = highlighter(msg)
        self.logger.info(msg.strip())
        result = self.external_exports
        self.logger.info("\tresolved: {}".format(result))
        return result

    __str__ = resolve

    @property
    def env_name(self):
        """extracts env name from argument"""
        tmp, _ = self.argument.split("::")[0].split("/")
        return tmp

    @property
    def stack_name(self):
        """extracts simple stack name from argument"""
        # return self.stack.name.split('/')[-1]
        _, tmp = self.argument.split("::")[0].split("/")
        return tmp

    @property
    def external_config(self):
        """get the full env-config for the external environment object"""
        s = SceptreContext(
            command_path=os.environ["SCEPTRE_ROOT"],
            project_path=os.environ["SCEPTRE_ROOT"],
        )
        conf_file = os.path.join(s.full_config_path(),
                                 self.env_name, "config.yaml")
        with open(conf_file, "r") as fhandle:
            return yaml.load(fhandle.read(), Loader=yaml.FullLoader)

    @property
    def external_connection_manager(self):
        """get a connection manager for the external env"""
        if self.env_name in CM_CACHE:
            return CM_CACHE[self.env_name]
        else:
            config = self.external_config
            CM_CACHE[self.env_name] = ConnectionManager(
                region=config["region"],
                iam_role=config.get("iam_role"),
                profile=config.get("profile"),
            )
            return self.external_connection_manager

    @property
    def full_stackname(self):
        """
        returns the full canonical external stack name
        (according to aws; none of the sceptre abbreviations)
        """
        if self.stack_name.startswith("eksctl"):
            return self.stack_name
        tmp = "{}-{}-{}".format(
            self.external_config["project_code"],
            self.env_name,
            self.stack_name.split(".")[0],
        )
        return tmp

    @property
    def external_exports(self):
        """get all the cf exports for the external stack"""
        cm = self.external_connection_manager
        all_exports = cm.call(
            service="cloudformation",
            command="describe_stacks",
            kwargs={"StackName": self.full_stackname},
        )
        all_exports = all_exports.get("Stacks", [{}])[0]
        all_exports = all_exports.get("Outputs", [])
        tmp = {}
        for dct in all_exports:
            tmp[dct["OutputKey"]] = dct["OutputValue"]
        return tmp


class StackExport(StackExports):
    """Returns one export from a given stack
    Usage:
        !stack_export env_name/stack_name::key_name
    """

    @property
    def cache_key(self):
        return (self.env_name, self.stack_name, self.key_name)

    @property
    def key_name(self):
        """extracts cf export key name from argument"""
        _, tmp = self.argument.split("::")
        return tmp

    def resolve(self):
        """main method for resolver"""
        from_cache = RESULTS_CACHE.get(self.cache_key)
        if not from_cache:
            msg = "resolving: {}".format((self.cache_key))
            self.logger.info(highlighter(msg).strip())
        if from_cache:
            # self.logger.debug("returning from cache")
            return from_cache
        try:
            result = self.external_exports[self.key_name]
        except KeyError:
            raise RuntimeError(
                f"could not find '{self.key_name}' in {self.env_name}/{self.stack_name} using {self.external_connection_manager}"
            )
        pretty_result = result
        if "," in result:
            pretty_result = json.dumps(result.split(","), indent=2)
        self.logger.info("  {}{}".format(util.bold(" ⇢  "), pretty_result))
        RESULTS_CACHE[self.cache_key] = result
        return result

    __str__ = resolve


class ThisStack(StackExport):
    """Shortcut to get an export from the current stack.

    Example usage:
        !this_stack KeyName
    """

    @property
    def env_name(self):
        return os.environ["env"]
        # return self.stack.stack_group_config['env_name']

    @property
    def stack_name(self):
        return os.environ["stack"]
        # return self.stack.name

    @property
    def key_name(self):
        return self.argument.strip()


class ThisEnv(StackExport):
    """Shortcut to get an export from the current env.

    Example usage:
        !this_env StackName::KeyName
    """

    @property
    def env_name(self):
        # return self.stack.stack_group_config['env_name']
        return os.environ["env"]

    @property
    def stack_name(self):
        return self.argument.strip().split("::")[0]
        # +'.yaml'
        # return os.environ['stack']

    @property
    def key_name(self):
        return self.argument.strip().split("::")[-1]


class StackOutputValuesFilter(StackExport):
    """
    General resolver that can help you filter all stack outputs,
    to for example, just return arn_exports.  You add other filters
    here if necessary.  Results will be returned as JSON strings.

    Usage example follows:

    sceptre_user_data:
      accesible_queues:
        dev: !stack_export_values_filter env_name/queues::is_arn
        qa: !stack_export_values_filter env_name/queues::is_arn
    """

    filters = dict(
        is_arn=lambda x: x.startswith("arn:aws:"),
    )

    def __init__(self, *args, **kwargs):
        super(StackOutputValuesFilter, self).__init__(*args, **kwargs)
        self.filter_name = self.key_name
        if self.filter_name not in self.filters:
            err = "No such value filter '{}' found in {}"
            raise ValueError(err.format(self.filter_name, self.filters))

    def resolve(self):
        """main method for resolver"""
        msg = "{}: resolving: {}".format(
            __name__, [self.env_name, self.stack_name]
        ).strip()
        self.logger.info(highlighter(msg).strip())
        # self.logger.debug('{}: external environment: {}'.format(__name__, self.env))
        all_exports = list(self.external_exports.values())
        arn_exports = list(filter(self.filters[self.filter_name], all_exports))
        return json.dumps(arn_exports)

    __str__ = resolve


class StackExportAsList(StackExport):
    """ """

    def resolve(self, *args, **kargs):
        result = super(StackExportAsList, self).resolve(*args, **kargs)
        result = result.split(",")
        return result


class ArpdFromArn(StackExport):
    """
    Usage example follows:
      iam_roles:
        FooBar:
          inlined_policy: !policy whatever/whatever.json.j2
          assume_role_policy_document: !arpd_from_arn env/appserver-foo-bar::Role
    """

    def resolve(self):
        result = super(ArpdFromArn, self).resolve()
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": result},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        )
