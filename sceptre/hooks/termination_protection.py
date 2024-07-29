"""
Provide utility hooks for operating on stacks.
"""

from __future__ import absolute_import
from sceptre.hooks import Hook

# from sceptre.environment import Environment


class SetStackTerminationProtection(Hook):
    """
    Enable/disable stack termination protection.
    """

    ALLOWED_ARG_VALUES = ["enabled", "disabled"]

    def __init__(self, *args, **kwargs):
        super(SetStackTerminationProtection, self).__init__(*args, **kwargs)

    def run(self):
        argument = (self.argument if self.argument else "").lower()

        assert (
            argument in self.ALLOWED_ARG_VALUES
        ), "As the argument for !set_stack_termination_protection, please choose one of {0}".format(
            self.ALLOWED_ARG_VALUES
        )
        raise RuntimeError("hook not reimplemented since upgrade!")
        # environment = Environment(
        #     self.environment_config.sceptre_dir,
        #     self.environment_config.environment_path)
        # stack = environment.stacks[os.environ['stack']]
        # cf_stack_name = stack.external_name
        #
        # enable = argument == 'enabled'
        #
        # self.logger.info(
        #     "Setting termination protection of stack '%s' to '%s'",
        #     cf_stack_name, argument)
        #
        # self.stack.connection_manager.call('cloudformation', 'update_termination_protection',
        #                              kwargs={
        #                                  'StackName': cf_stack_name,
        #                                  'EnableTerminationProtection': enable
        #                              })
