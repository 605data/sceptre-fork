"""
This sceptre hook exposes a subset of ansible functionality for simple
use-cases where you have 1:1 relationships between the sceptre stack
and the ec2 host you want to provision.  It's not suitable for complex
use-cases where you need things like full-on inventories or group vars.
"""

from __future__ import absolute_import
from devops import (
    util,
)
import os
from sceptre.hooks import Hook
import six
import botocore
import sys
import json

SCEPTRE_ROOT = os.environ["SCEPTRE_ROOT"]
ANSIBLE_ROOT = os.environ.get(
    "ANSIBLE_ROOT", os.path.join(os.path.dirname(SCEPTRE_ROOT), "ansible")
)


LOGGER = util.get_logger("hooks." + __name__)


class ansible_provisioner(Hook):
    def __init__(self, *args, **kwargs):
        super(ansible_provisioner, self).__init__(*args, **kwargs)

    def return_or_resolve(self, val):
        """
        check whether given value is a string because this might, and often
        should be, a lazy sceptre value from something like `!stack_export`

        FIXME: function is not DRY across all hooks
        """
        if isinstance(val, (dict,)):
            # proper recursive resolution/encoding.
            # previously we punted and dumped json here
            # but that's a hack, lets see if this works better.
            return dict([[k, self.return_or_resolve(v)] for k, v in val.items()])
        elif isinstance(val, (list,)):
            return [self.return_or_resolve(x) for x in val]
        elif isinstance(val, (six.string_types, int, float)):
            return val
        else:
            return val.resolve()
            # raise Exception("not implemented for `{}`, type {/}".format(val, type(val)))

    @property
    def ansible_tags(self):
        main_arg = self.argument or ""
        tags_arg = [
            arg.strip()
            for arg in main_arg.strip().split(" ")
            if arg.strip() and arg.startswith("tags=")
        ]
        tags_arg = tags_arg and tags_arg[0].split("tags=")[-1]
        return (tags_arg or os.environ.get("ANSIBLE_TAGS", "all")).split(",")

    @property
    def ansible_host_list(self):
        cfg = self.stack.raw_config["ansible"]
        hosts = cfg.get("hosts", [])
        assert isinstance(hosts, (list,)), "ansible::hosts should be a list!"
        if "host" in cfg:
            hosts.append(cfg["host"])
        hosts = [self.return_or_resolve(host) for host in hosts]
        hosts = flatten(hosts)
        hosts.append("")
        return ",".join(hosts)

    @property
    def ansible_inventory(self):
        """ """
        cfg = self.stack.raw_config["ansible"]
        rel_inventory = cfg.get("inventory")
        if rel_inventory == "local,":
            return rel_inventory
        if rel_inventory:
            err = "ansible::inventory should be a string!"
            assert isinstance(rel_inventory, (six.string_types,)), err
            abs_inventory = os.path.join(ANSIBLE_ROOT, rel_inventory)
            err = "inventory does not exist at {}".format(abs_inventory)
            assert os.path.exists(abs_inventory), err
            return abs_inventory

    @property
    def ansible_vars(self):
        """ """
        ansible_vars = {}
        stack_ansible_vars = self.stack.raw_config["ansible"]["vars"]
        # add sceptre_* vars from top-level env config
        for k, v in self.stack.stack_group_config.items():
            if isinstance(v, (dict, list, bool)):
                # these are complex types, so we
                # mark them special by keying them with `None`
                ansible_vars[None] = ansible_vars.get(None, []) + [
                    json.dumps({k: self.return_or_resolve(v)})
                ]
            else:
                ansible_vars["sceptre_" + k] = v
        # add stack-level ansible vars from `ansible:` section
        LOGGER.debug("parsing ansible variables passed from stack..")
        for k, v in stack_ansible_vars.items():
            if hasattr(v, "resolve"):
                v = v.resolve()
            LOGGER.debug("  - {} = {}".format(k, v))
            if isinstance(v, (dict, list, bool)):
                # these are complex types, so we
                # mark them special by keying them with `None`
                ansible_vars[None] = ansible_vars.get(None, []) + [
                    json.dumps({k: self.return_or_resolve(v)})
                ]
            else:
                ansible_vars[k] = self.return_or_resolve(v)
        # next block passes tags from the sceptre stack into ansible.
        # besides resolving any lazy values, we also need to use the
        # special pure JSON format for passing data to ansible because
        # the simpler `--extra-vars foo=bar` format won't work for
        # complex data.  to indicate this is not a simple key/value
        # --extra-var, we use the special key `None`.  see the other
        # usage of `special` inside the `run()` method
        stack_tags = self.stack.tags
        special = ansible_vars.get(None, [])
        special += [
            json.dumps(
                dict(
                    sceptre_stack_tags=dict(
                        [[k, self.return_or_resolve(v)]
                         for k, v in stack_tags.items()]
                    )
                )
            )
        ]
        ansible_vars[None] = special
        # as of newer sceptre, these are attached to the stack
        # object and no longer exposed in the stack vars
        ansible_vars["sceptre_profile"] = self.stack.profile
        ansible_vars["sceptre_region"] = self.stack.region
        return ansible_vars

    @property
    def ansible_playbook(self):
        rel_playbook = self.stack.raw_config["ansible"]["playbook"]
        abs_playbook = os.path.join(ANSIBLE_ROOT, rel_playbook)
        err = 'playbook "{0}" is missing!'.format(abs_playbook)
        assert os.path.exists(abs_playbook), err
        return rel_playbook

    def run(self):
        """
        The following attributes may be available from the base class:
        self.stack_config  (A dict of data from <stack_name>.yaml)
        self.connection_manager (A connection_manager)
        """
        try:
            ansible_host_list = self.ansible_host_list
        except botocore.exceptions.ClientError as exc:
            LOGGER.exception(exc)
            error = exc.response["Error"]
            if (
                error["Code"] == "ValidationError"
                and "does not exist" in error["Message"]
            ):
                if "IGNORE_MISSING_STACK" in os.environ:
                    LOGGER.info(
                        "IGNORE_MISSING_STACK is defined, ignoring missing stack..."
                    )
                    return sys.exit(0)
            pass
        ansible_inventory = self.ansible_inventory or self.ansible_host_list
        ansible_limit = ansible_host_list if self.ansible_inventory else ""
        ansible_limit = ("-l " + ansible_limit) if ansible_limit else ""

        ansible_playbook = self.ansible_playbook
        ansible_check = "--check" if "ANSIBLE_DRY_RUN" in os.environ else ""
        msg = "{}: will provision `{}` with `{}`"
        LOGGER.info(msg.format(__name__, ansible_host_list, ansible_playbook))
        if os.environ.get("PROVISION_NOOP", None):
            LOGGER.info("{}: skipping, PROVISION_NOOP is set".format(__name__))
            return
        ansible_verbose = "-vvvvv" if os.environ.get("ANSIBLE_VERBOSE") else ""
        ansible_tags = self.ansible_tags
        ansible_tags = ",".join(self.ansible_tags)
        ansible_vars = self.ansible_vars
        special = ansible_vars.pop(None, [])
        ansible_vars = ["-e '{0}={1}'".format(k, v)
                        for k, v in ansible_vars.items()]
        ansible_vars += ["-e '{}'".format(x) for x in special]
        src_root = os.environ.get("SRC_ROOT")
        if src_root:
            ansible_vars += ["-e 'src_root={}'".format(src_root)
                             for x in special]
        ansible_vars = " ".join(ansible_vars)
        if "ANSIBLE_TAGS" in os.environ:
            ansible_skip_tags = "--skip-tags untagged"
        else:
            ansible_skip_tags = os.environ.get("ANSIBLE_SKIP", "")
        cmd = (
            "cd {ANSIBLE_ROOT} && "
            "ansible --version && "
            "AWS_PROFILE={AWS_PROFILE} "
            "AWS_DEFAULT_REGION={AWS_REGION} \\"
            "\nansible-playbook {ansible_verbose} "
            "{ansible_limit} -i {ansible_inventory} "
            "{ansible_vars} -e @vars-common.yml "
            "{ansible_check} "
            "{ansible_skip_tags} "
            "--tags {ansible_tags} "
            "{ansible_playbook}"
        ).format(
            ANSIBLE_ROOT=ANSIBLE_ROOT,
            AWS_PROFILE=self.stack.profile,
            AWS_REGION=self.stack.region,
            ansible_inventory=ansible_inventory,
            ansible_limit=ansible_limit,
            # ansible_host_list=ansible_host_list,
            ansible_vars=ansible_vars,
            ansible_verbose=ansible_verbose,
            ansible_tags=ansible_tags,
            ansible_skip_tags=ansible_skip_tags,
            ansible_check=ansible_check,
            ansible_playbook=ansible_playbook,
        )
        LOGGER.warn("")
        LOGGER.warn("EXEC ⇨")
        LOGGER.warn("\n{}".format(cmd))
        LOGGER.warn("")
        error = os.system(cmd)
        if error:
            channel = LOGGER.warn
        else:
            channel = LOGGER.info
        channel("")
        channel("EXEC FINISHED: \n{}".format(cmd))
        channel("(success)" if not error else "(exit code: {})".format(error))
        if error:
            raise SystemExit("error {}".format(error))


def flatten(hosts):
    rt = []
    for host in hosts:
        if isinstance(host, list):
            rt.extend(flatten(host))
        else:
            rt.append(host)
    return rt
