# -*- coding: utf-8 -*-
"""
This file is part of the mechanism for enabling IP source restrictions to IAM.
See https://github.com/605data/infra-docs/blob/master/iam.md#ip-source-restrictions

This sceptre resolver is basically just a proxy to devops.netops.api.describe_edge_cidrs
See also: python-devops.git/devops/netops/api
"""

from __future__ import absolute_import
import json

from sceptre.resolvers import Resolver

from devops import (
    util,
)
from devops.netops import api

LOGGER = util.get_logger(__name__)


class sixzerofive_edge_cidrs(Resolver):
    def resolve(self):
        """get the policy file from `policy_root`, and return it,
        rendering it with the standard context if applicable
        """
        LOGGER.debug(
            "looking up edge cidrs with devops.netops.api.describe_edge_cidrs.."
        )
        result = api.describe_edge_cidrs()["ipv4"]
        LOGGER.debug(
            "done computing edge cidrs: \n\t{}".format(
                json.dumps(result, indent=2))
        )
        return json.dumps(result)
