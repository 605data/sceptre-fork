"""
this file implements `!value_from_ssm`, which resolves secrets from SSM
and inserts them into sceptre (and therefore cloudformation) runtimes
"""
from __future__ import absolute_import
import boto3
from sceptre.resolvers import Resolver


class value_from_ssm(Resolver):
    session_cache = {}

    def __init__(self, *args, **kwargs):
        super(value_from_ssm, self).__init__(*args, **kwargs)

    def resolve(self):
        """
        resolve is the method called by Sceptre. It should carry out the work
        intended by this resolver. It should return a string to become the
        final value.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)

        The following attributes may be available from the base class:
        self.stack.raw_config  (A dict of data from <stack_name>.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        try:
            profile, path = self.argument.split()
            profile, region = profile.split("@")
        except ValueError:
            raise ValueError(
                "Bad syntax for the !value_from_ssm "
                " resolver. Use it like this: '!value_from_ssm "
                "profile_name@region /some/ssm/path'"
            )
        self.logger.info("resolving {0} with {1}".format(path, profile))
        if profile not in self.session_cache:
            self.logger.info("caching session for profile {}".format(profile))
            self.session_cache[profile] = boto3.session.Session(
                region_name=region, profile_name=profile
            )
        session = self.session_cache[profile]
        client = session.client("ssm")
        try:
            return client.get_parameter(Name=path, WithDecryption=True)["Parameter"][
                "Value"
            ]
        except Exception as exc:
            # Prevents sceptre from doing something wonky that obscures
            # how this error is coming from this resolver
            err = "Error looking up parameter {} Original Exception follows: {}"
            raise RuntimeError(err.format([region, profile, path], exc))
