"""
    A resolver for grabbing keys from external serverless stacks.

    See https://github.com/605data/serverless/ project README for more details.

    Usage:

        !serverless env_name/serverless_stage_name/project_name::CloudformationKeyName

    Or, if the env_name/serverless_stage_name are the same:

        !serverless serverless_stage_name/project_name::CloudformationKeyName
"""
from __future__ import absolute_import
import os
import subprocess
from sceptre.resolvers import Resolver
from devops import (
    util,
)
from devops.environment import Environment

from pygments import highlight, lexers, formatters

PYGMENTS_LEXER = lexers.PythonLexer()
PYGMENTS_FORMATTER = formatters.Terminal256Formatter(style="rrt")


def highlighter(x):
    return highlight(x, PYGMENTS_LEXER, PYGMENTS_FORMATTER)


def snake(name):
    # FIXME: move to common libs
    import re

    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return name


usage_error = (
    "resolvers.serverless expects either "
    "'!serverless env_name/serverless_stage/project_name::key' or else "
    "'!serverless env/project_name::key' (where `serverless_stage` is assumed to be the same as `env`)"
)


class serverless(Resolver):
    def __init__(self, *args, **kwargs):
        super(serverless, self).__init__(*args, **kwargs)
        tmp_name = "resolvers."
        tmp_name += os.path.splitext(os.path.basename(__file__))[0]
        tmp_name += "." + snake(__name__)
        self.logger = util.get_logger(tmp_name)

    def resolve(self):
        """ """
        args = self.argument.split("/")
        if len(args) == 3:
            env_name, serverless_stage_name, last_part = args
        elif len(args) == 2:
            msg = "environment name not provided, assuming serverless stack is in this environment!"
            self.logger.warning(msg)
            env_name = self.stack.stack_group_config["env_name"]
            serverless_stage_name, last_part = self.argument.split("/")
        else:
            raise ValueError(usage_error)
        try:
            lambda_name, export_key = last_part.split("::")
        except (ValueError,):
            raise ValueError(usage_error)
        req = dict(
            env=env_name,
            stage=serverless_stage_name,
            project=lambda_name,
            key=export_key,
        )
        msg = "resolving: {}".format(str(req)).strip()
        self.logger.info(highlighter(msg).strip())
        serverless_stack_name = "serverless-{}-{}".format(
            lambda_name, serverless_stage_name
        )
        self.logger.info(
            "serverless stack is: {}".format(serverless_stack_name))
        env_obj = Environment.from_name(env_name)
        client = env_obj.cloudformation
        serverless_stacks = client.describe_stacks(StackName=serverless_stack_name)[
            "Stacks"
        ]
        try:
            serverless_stack = serverless_stacks[0]
        except (IndexError,):
            err = "No serverless stack named {} could be found in environment {}"
            self.logger.warning(err.format(serverless_stack_name, env_name))
            raise
        result = None
        for output in serverless_stack["Outputs"]:
            if output["OutputKey"] == export_key:
                result = output
                break
        if result is None:
            err = "No output named {} was found in serverless stack named {} inside environment {}"
            self.logger.warning(err.format(
                export_key, serverless_stack_name, env_name))
            raise ValueError(err)
        result = result["OutputValue"]
        if export_key == "MainLambdaFunctionQualifiedArn":
            # special case, here we chop off the last part of the arn,
            # which is the lambda version number, because this is what
            # we usually want (all versions)
            result = ":".join(result.split(":")[:-1])
        self.logger.info("\tresolved: {}".format(result))
        return result
