"""
This sceptre hook does nothing but run the other hooks mentioned in the
`provisioners` section.  This is so provisioners can be declared and run
with a command like 'env=legacy stack=appserver make provision'.
"""

from __future__ import absolute_import
import os

import sceptre
from sceptre.hooks import Hook
from devops import (
    util,
)

SCEPTRE_ROOT = os.environ["SCEPTRE_ROOT"]

ANSIBLE_ROOT = os.environ.get(
    "ANSIBLE_ROOT", os.path.join(os.path.dirname(SCEPTRE_ROOT), "ansible")
)

LOGGER = util.get_logger("hooks.provision")

# quiet logs if running from atlantis
if os.environ.get("ATLANTIS_LOG_LEVEL"):
    LOGGER.info = lambda *args, **kwargs: None
    LOGGER.debug = lambda *args, **kwargs: None


class provision(Hook):
    def __init__(self, *args, **kwargs):
        super(provision, self).__init__(*args, **kwargs)
        LOGGER.info("initializing")

    def run(self):
        """
        The following attributes may be available from the base class:
        self.stack.raw_config  (A dict of data from <stack_name>.yaml)
        self.environment_config  (A dict of data from config.yaml)
        self.stack.connection_manager (A connection_manager)
        """
        # here we just chain to the external fxn
        provision_stack(self.stack)


@util.timeit
def provision_stack(stack):
    """external function so that this file
    can also be used as a stand-alone script.
    see invocation from __main__
    """
    provisioners = stack.hooks.get("provisioners", [])
    if not isinstance(provisioners, (list,)):
        raise ValueError("expected `provisioners` section should be a list!")
    if not provisioners:
        LOGGER.error("stack.hooks.provisioners is empty!")
        return
    else:
        for provisioner in provisioners:
            if provisioner.__class__ == provision:
                LOGGER.warning(
                    "Skipping, not a provisioner!: {}".format(
                        provisioner.__class__)
                )
                continue
            LOGGER.warning("DISPATCHING {}".format(
                provisioner.__class__.__name__))
            error = provisioner.run()
            if error:
                raise SystemExit("SystemExit: {}".format(error))
            LOGGER.warning("")
            LOGGER.warning("FIN DISPATCHING {}".format(
                provisioner.__class__.__name__))


if __name__ == "__main__":
    from sceptre.context import SceptreContext
    from sceptre.plan.plan import SceptrePlan

    context = SceptreContext(
        command_path="{}/{}.yaml".format(
            os.environ["env"], os.environ["stack"]),
        project_path=os.environ["SCEPTRE_ROOT"],
        user_variables={},
        ignore_dependencies=True,
    )
    plan = SceptrePlan(context)
    stack = list(plan.command_stacks)[0]
    provision_stack(stack)
