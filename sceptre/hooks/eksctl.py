"""
Hook that runs the given eksctl command with the current stacks EKS config.

See also:
   https://eksctl.io/usage/schema/ and
   https://github.com/weaveworks/eksctl/blob/master/examples/


Example usage:
    - !eksctl create
    - !eksctl update
    - !eksctl delete
"""

from __future__ import absolute_import

import os
import yaml
import json

from sceptre.hooks import Hook

from devops import util
from devops.util import sceptre as sceptre_util
from devops.api.ecr import ecr_login

LOGGER = util.get_logger("hooks." + __name__)

EKSCTL_CONTAINER = "public.ecr.aws/eksctl/eksctl:v0.183.0"


class eksctl(Hook):
    def run(self):
        """api interface, this is overriden from parent"""
        expected = "create update delete tag".split()
        if self.argument not in expected:
            LOGGER.critical("expected one of {}".format(expected))
            raise SystemExit(1)
        LOGGER.debug("dispatching to `{}`".format(self.argument))
        dispatch = getattr(self, self.argument)
        error = dispatch()
        if error:
            raise SystemExit(1)

    @property
    def eksctl_user_data(self):
        """
        returns a fully resolved version of the `eksctl_user_data`
        that is embedded inside this stack
        """
        data = self.stack.raw_config["eksctl_user_data"]
        return sceptre_util.return_or_resolve(data)

    @property
    def cluster_name(self):
        """
        helper for pulling cluster name from the eksctl config.
        NB: path below is demanded by, but coupled to, eksctl config schema
        """
        return self.stack.raw_config["sceptre_user_data"]["eksctl_user_data"][
            "metadata"
        ]["name"]

    @property
    def cluster_arn(self):
        """ """
        return "arn:aws:eks:{}:{}:cluster/{}".format(
            self.stack.region,
            self.stack.stack_group_config["account_id"],
            self.cluster_name,
        )

    def write_eksctl_config(self):
        """ """
        outfile = "~/.kube/.eksctl.{}.{}.yaml".format(
            os.environ["env"], self.cluster_name
        )
        data = self.eksctl_user_data
        msg = "extracted eksctl user data:\n\n{}"
        LOGGER.debug(msg.format(json.dumps(data, indent=2)))
        LOGGER.debug("writing contents to:")
        LOGGER.debug("  `{}`".format(outfile))
        with open(os.path.expanduser(outfile), "w") as yaml_file:
            yaml.dump(data, yaml_file, default_flow_style=False)
        return outfile

    @util.timeit
    def invoke_eksctl(self, cmd):
        """
        actually runs eksctl with the given command,
        for example `create-cluster`.  NB: some arguments
        are autogenerated/appended so you shouldn't pass them.
        """
        fname = self.write_eksctl_config()
        ecr_login()
        self.exec_cmd("docker pull {}".format(EKSCTL_CONTAINER))
        cmd = self.get_eksctl_invocation(cmd, config_file=fname)
        return self.exec_cmd(cmd)

    def exec_cmd(self, cmd):
        """ """
        LOGGER.warning("")
        LOGGER.warning("EXEC ⇨")
        LOGGER.warning("\n{}".format(cmd))
        LOGGER.warning("")
        LOGGER.debug("")
        return os.system(cmd)

    @property
    def docker_volume_root(self):
        """ """
        if "DOCKER_VOLUME_ROOT" in os.environ:
            tmp = os.environ["DOCKER_VOLUME_ROOT"]
            return tmp
        else:
            LOGGER.debug("DOCKER_VOLUME_ROOT is missing, using ~")
            return "~"

    def get_eksctl_invocation(self, cmd, config_file=None, dry_run=False):
        """returns a CLI suitable for running eksctl from docker"""
        cmd_t = (
            "{dry_run_maybe} docker run --entrypoint sh "
            "-v {docker_home}/.kube:/root/.kube "
            "-v {docker_home}/.aws:/root/.aws "
            "-v `pwd`:/workspace "
            "-w /workspace "
            '{container} -x -c "'
            'eksctl {cmd} --profile {profile} {file_maybe}"'
        )
        return cmd_t.format(
            profile=self.stack.profile,
            container=EKSCTL_CONTAINER,
            docker_home=self.docker_volume_root,
            cmd=cmd,
            dry_run_maybe="echo" if dry_run else "",
            file_maybe="--config-file {}".format(
                config_file) if config_file else "",
        )

    def tag(self):
        """
        NB: `tag` is not actually a eksctl subcommand, but the cf generated
             by the opaque eksctl backend does not support cluster tags.
        FIXME: tag removal is not actually supported
        """
        stack_tags = self.stack.tags
        LOGGER.debug(
            "propagating {} stack tags to cluster..".format(len(stack_tags)))
        cli_t = "AWS_PROFILE={} aws eks tag-resource --resource-arn {} --tags {}={}"
        errors = []
        for k, v in stack_tags.items():
            cmd = cli_t.format(self.stack.profile, self.cluster_arn, k, v)
            err = self.exec_cmd(cmd)
            errors += [err]
        if any(errors):
            LOGGER.warning("✘ failed updating cluster tags")
        else:
            LOGGER.debug("☑ cluster-tagging was completed successfully")

    def create(self):
        """ """
        return self.invoke_eksctl("create cluster")

    def delete(self):
        """ """
        return self.invoke_eksctl("delete cluster --wait")

    def update(self):
        """ """
        return self.invoke_eksctl("update cluster")