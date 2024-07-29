"""
this is a hook that just runs the given AWS command with the same AWS_PROFILE
as the current environment settings uses.
"""

from __future__ import absolute_import
from sceptre.hooks import Hook
from devops import (
    util,
)
from multiprocessing.dummy import Pool as ThreadPool


class roles_tags(Hook):
    def __init__(self, *args, **kwargs):
        super(roles_tags, self).__init__(*args, **kwargs)

    def run(self):
        """
        run is the method called by Sceptre. It should carry out the work
        intended by this hook.

        self.argument is available from the base class and contains the
        argument defined in the sceptre config file (see below)

        The following attributes may be available from the base class:
        self.stack_config  (A dict of data from <stack_name>.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        # anything to just cache a client session early
        self.stack.connection_manager.call("iam", "list_groups", kwargs={})
        self.logger.info(
            "Running hook {} against {}".format(
                util.blue(__name__), self.stack.profile)
        )

        # AWS allows commas in some tags, but not others,
        # so we have to sanitize input a little bit
        stack_tags = dict(
            [[k, v] for k, v in self.stack.tags.items() if "," not in str(v)]
        )
        if not stack_tags:
            self.logger.warning("\tno tags found for stack!")
            return
        # self.handle_role_property(stack_tags)
        # self.handle_iam_roles_property(stack_tags)
        # self.handle_inlined_iam_roles_property(stack_tags)
        pool = ThreadPool(20)
        pool.map(self.handle_role_property, [stack_tags])
        pool.close()
        pool.join()
        pool = ThreadPool(20)
        pool.map(self.handle_iam_roles_property, [stack_tags])
        pool.close()
        pool.join()
        pool = ThreadPool(20)
        pool.map(self.handle_inlined_iam_roles_property, [stack_tags])
        pool.close()
        pool.join()

    @property
    def user_data(self):
        return self.stack.raw_config

    def handle_role_property(self, stack_tags):
        if "role" not in self.user_data or not self.user_data["role"]:
            self.logger.warning(
                "\tno top level `role` property found in stack")
            return
        role = self.user_data["role"]
        final_role_name = self.append_605_prefix(role["name"])
        tags = [{"Key": k, "Value": str(v)} for k, v in stack_tags.items()]
        self.logger.info(
            "\ttagging {} with {}".format(
                final_role_name, ",".join(util.tags_list_to_dict(tags).keys())
            )
        )
        self.stack.connection_manager.call(
            "iam", "tag_role", kwargs=dict(RoleName=final_role_name, Tags=tags)
        )

    def handle_iam_roles_property(self, stack_tags):
        """ """
        if "iam_roles" not in self.user_data or not self.user_data["iam_roles"]:
            self.logger.warning(
                "\t.. no top level `iam_roles` property found in stack")
            return
        roles = self.user_data["iam_roles"]
        self.logger.info(util.green("\thandling `iam_roles` property.."))
        for role_name, metadata in roles.items():
            final_role_name = self.append_605_prefix(role_name)
            tags = [{"Key": k, "Value": str(v)} for k, v in stack_tags.items()]
            self.logger.info(
                "\t\ttagging `{}` with: {}".format(
                    util.blue(final_role_name), ",".join(stack_tags.keys())
                )
            )
            self.stack.connection_manager.call(
                "iam", "tag_role", kwargs=dict(RoleName=final_role_name, Tags=tags)
            )

    def handle_inlined_iam_roles_property(self, stack_tags):
        """ """
        if "iam_roles" not in self.user_data or not self.user_data["iam_roles"]:
            self.logger.warning(
                "\t no top level `iam_roles` property in stack")
            return
        roles = self.user_data["iam_roles"]
        self.logger.info(
            util.green("\thandling tags for top level `iam_roles` property..")
        )
        for role_name, metadata in roles.items():
            if "tags" not in metadata or not metadata["tags"]:
                self.logger.warning(
                    "\t\tno inlined tags for {}".format(role_name))
                continue
            final_role_name = self.append_605_prefix(role_name)
            local_tags = metadata["tags"]
            self.logger.info(
                "\t\ttagging `{}` with: {}".format(
                    util.blue(final_role_name), ",".join(local_tags.keys())
                )
            )
            tags = [{"Key": k, "Value": str(v)} for k, v in local_tags.items()]
            self.stack.connection_manager.call(
                "iam", "tag_role", kwargs=dict(RoleName=final_role_name, Tags=tags)
            )

    def append_605_prefix(self, name):
        return "605-{}".format(name)  # we append 605- prefix in templates
