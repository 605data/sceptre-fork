"""
this is a hook that uses existing hooks to perform a set  of commands
required to dafely delete eks cluster

Example usage:
    - !ekscleanup ...
"""

from __future__ import absolute_import
import time
import os
from helm import EksHook
from sceptre.hooks import Hook
from devops import util


LOGGER = util.get_logger("hooks." + __name__)


class ekscleanup(EksHook):
    def run(self):
        """api interface, this is overriden from parent"""
        # Below logic:
        # get all charts | remove header | extract namespace and name | filter out SSM and ALB stuff to let those controllers clean resources | pass to helm delete
        self.argument = 'helm list --all-namespaces | tail -n +2 | awk "{print \$2,\$1}" | grep -Ev "ssm|kube-system" | xargs -n2 -t helm delete -n || exit 0'  # noqa
        self.invoke_helm()

        kubectl_cmds = [
            # drop all ArgoCD related things to prevent auto-recreation of resources
            "kubectl delete namespace argocd || exit 0",
            "kubectl delete namespaces --all-namespaces --field-selector metadata.name!=default,metadata.name!=ssm,metadata.name!=external-dns,metadata.name!=kube-public,metadata.name!=kube-system,metadata.name!=kube-node-lease",
        ]

        for cmd in kubectl_cmds:
            self.argument = cmd
            self.invoke_kubectl()

        # Wait for resources like DNS or SGs to be dropped by controllers
        time.sleep(60)

        # Drop external-dns
        self.argument = "kubectl delete namespace external-dns || exit 0"
        self.invoke_kubectl()

        # Delete all hanging charts like SSM or ALB ingress controller
        self.argument = 'helm list --all-namespaces | tail -n +2 | awk "{print \$2,\$1}" | xargs -n2 -t helm delete -n || exit 0'  # noqa
        self.invoke_helm()

    @util.timeit
    def invoke(self, cmd):
        """runs command with the usual wrapper for logging"""
        LOGGER.warning("")
        LOGGER.warning("EXEC ⇨")
        LOGGER.warning("\n{}".format(cmd))
        LOGGER.warning("")
        LOGGER.debug("")
        return os.system(cmd)
