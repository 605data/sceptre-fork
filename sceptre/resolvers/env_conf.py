"""
"""
from __future__ import absolute_import
import os
import yaml
from sceptre.resolvers.stack_output import Resolver
from sceptre.context import SceptreContext

from devops import (
    util,
)

ENV_CACHE = {}
CM_CACHE = {}
RESULTS_CACHE = {}

# use our  logger, the formatter is nicer than sceptre
LOGGER = util.get_logger(__name__)


class EnvConf(Resolver):
    """Returns matching vaalue for a given env/var-name
    (this uses cloudformation/config/env_name/config.yaml under the hood)
    usage:
        !env_conf env_name::var_name
    """

    env_cache = {}
    cm_cache = {}

    def __init__(self, *args, **kwargs):
        # argument = kwargs.pop('argument', None)
        super(EnvConf, self).__init__(*args, **kwargs)

    def resolve(self):
        """main method for resolver"""
        LOGGER.info("resolving: {}".format([self.env_name, self.var_name]))
        # import json
        # LOGGER.info('from: {}'.format(json.dumps(list(self.env_config.items()), indent=2)))
        result = self.env_config[self.var_name]
        LOGGER.info("\tresolved: {}".format(result))
        return result

    __str__ = __repr__ = resolve

    @property
    def env_name(self):
        """extracts env name from argument"""
        tmp, _ = self.argument.split("/")
        return tmp.strip()

    @property
    def var_name(self):
        """extracts simple stack name from argument"""
        _, tmp = self.argument.split("/")
        return tmp.strip()

    @property
    def env(self):
        """
        returns an object for the external environment we care
        about to resolve the export mentioned by self.argument
        """
        s = SceptreContext(
            command_path=os.environ["SCEPTRE_ROOT"],
            project_path=os.environ["SCEPTRE_ROOT"],
        )
        conf_file = os.path.join(s.full_config_path(),
                                 self.env_name, "config.yaml")
        with open(conf_file, "r") as fhandle:
            return yaml.load(fhandle.read(), Loader=yaml.FullLoader)
        # if self.env_name not in ENV_CACHE:
        #     # block duplicated in hooks/provision.py; this is ugly but
        #     # prevents further divergence from upstream in our sceptre fork
        #     assert sceptre.__version__ == '1.3.4'
        #     ENV_CACHE[self.env_name] = cli.get_env(
        #         os.environ['SCEPTRE_ROOT'],
        #         self.env_name, {})
        # return ENV_CACHE[self.env_name]

    @property
    def env_config(self):
        """get the full env-config for the external environment object"""
        return self.env
