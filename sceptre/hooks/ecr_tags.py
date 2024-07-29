"""
This is a hook that runs the given AWS command with the same AWS_PROFILE
as the current environment settings uses.

FIXME: this won't work with the cross account role!

"""

from __future__ import absolute_import
import os
from sceptre.hooks import Hook

ECR_PROFILE = "605-shared-services"
ECR_ACCOUNT_ID = "870326185936"
ECR_REGION = "us-east-2"
ECR_BASE = "{}.dkr.ecr.{}.amazonaws.com".format(ECR_ACCOUNT_ID, ECR_REGION)

PULLED = False


class ecr_tags(Hook):
    @property
    def image(self):
        return "{}/605data/awscli:605".format(ECR_BASE)

    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)
        """
        repos = self.stack.raw_config["sceptre_user_data"]["repositories"]
        docker_login_cmd = "$(AWS_PROFILE={} aws ecr get-login-password --region {} --registry-ids {})"
        docker_login_cmd = docker_login_cmd.format(
            ECR_PROFILE, ECR_REGION, ECR_ACCOUNT_ID
        )
        docker_commands = [docker_login_cmd,
                           "docker pull {}".format(self.image)]
        tag_commands = []
        for repo_name, metadata in repos.items():
            tags = metadata.get("tags", {})
            tags = ['Key={},Value="{}"'.format(k, v) for k, v in tags.items()]
            if tags:
                repo_arn = "arn:aws:ecr:{}:{}:repository/{}".format(
                    ECR_REGION, ECR_ACCOUNT_ID, repo_name
                )
                self.logger.info("{}: {} at {}".format(
                    __name__, repo_name, repo_arn))
                for tag in tags:
                    tag_commands.append(
                        "aws ecr tag-resource --resource-arn {} --tags '{}'".format(
                            repo_arn, tag
                        )
                    )
        tag_commands = " && ".join(tag_commands)
        docker_commands.append(
            (
                "docker run -e AWS_PROFILE={} -e AWS_DEFAULT_REGION={} "
                "--entrypoint sh -v ~/.aws:/root/.aws:ro {} {}"
            ).format(
                ECR_PROFILE, ECR_REGION, self.image, '-x -c "{}"'.format(
                    tag_commands)
            )
        )
        cmd = " && ".join(docker_commands)
        self.logger.warn("{}: EXEC: {}".format(__name__, cmd))
        error = os.system(cmd)
        if error:
            raise SystemExit(error)
        # FIXME: remove tags missing from stack config
