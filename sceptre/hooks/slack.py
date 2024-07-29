##
# !slack is a hook that sends stack-update events to slack #infrabots
##
from __future__ import absolute_import
import os
from sceptre.hooks import Hook
from devops import (
    environment,
)

Env = environment.Environment


class slack(Hook):
    """ """

    def __init__(self, *args, **kwargs):
        super(slack, self).__init__(*args, **kwargs)

    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)

        The following attributes may be available from the base class:
        self.stack.raw_config  (A dict of data from <stack_name>.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        if "SLACK_DEBUG" in os.environ:
            self.logger.info("SLACK_DEBUG is set, leaving early")
            return
        msg = (
            "sending slack notifications "
            "(this is not required for stack update success)"
        )
        self.logger.info(msg)
        ecr = Env.from_name("shared-services").ecr
        # remote_cmd='git config --get remote.origin.url'
        # remote = util.invoke(remote_cmd).stdout.strip()
        # this_repo = os.path.splitext(
        #     os.path.basename(remote)[0])
        ecr.run(
            pull=True,
            login=True,
            proxy_aws_config=True,
            container="python-devops",
            tag="chatops",
            environment=dict(
                BUILD_URL=os.environ.get("BUILD_URL", "??"),
                SLACK_CHANNEL="infra-bots",
                # EVENT_DATA=json.dumps(dict(
                #     repo=this_repo
                # ))
            ),
            entrypoint="chatops",
            subcommand="event --type {}".format(self.get_event_type()),
        )

    def get_event_type(self):
        """
        use the os/sceptre context to automatically build
        the event-type string.  slack users may subscribe
        to this event type (or a regex that matches it) in
        https://github.com/605data/chat-ops/tree/master/event-subscriptions.yml
        """
        event_type = "{}-{}-{}".format(
            os.environ["env"], os.environ["stack"], self.get_hook_type()
        )
        self.logger.info("event type: {0}".format(event_type))
        return event_type

    def get_hook_type(self):
        """
        dynamically build a string that returns the hook type
        for the currently executing hook.  this value is one
        of `before_update`, etc.  see also the docs here:
        https://sceptre.cloudreach.com/latest/docs/hooks.html
        """
        all_hooks = self.stack.raw_config["hooks"]
        sceptre_hook_type = "unknown"
        for hook_name, hook_objects in all_hooks.items():
            hook_objects = hook_objects or []
            if self in hook_objects:
                sceptre_hook_type = hook_name
        self.logger.info("detected hook type: {0}".format(sceptre_hook_type))
        return sceptre_hook_type
