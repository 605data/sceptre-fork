"""
this file implements `!lookup_ami`, which checks for latest instance AMI based on tags
and inserts it into sceptre (and therefore cloudformation) runtimes
"""
from __future__ import absolute_import
import os
import boto3
from sceptre.resolvers import Resolver
from dateutil import parser
from devops import (
    util,
)

# Details below are used to get a EC2 client and fill in the details for AMI
# query.  It seems like they *must* match the place where AMI was actually
# baked (which is always management, see for more details the overview
# here https://github.com/605data/infra-docs/blob/master/ami-bakery.md
#
# For example, even when an AMI is shared from management to legacy, the
# query does not seem to work using a legacy profile and filtering for
# management as an owner.  Is this a problem in our packer configs?

# Hardcoded values for management and legacy accounts
AWS_ACCOUNT_ID = ["873326152210", "248783370565"]
AWS_PROFILE = ["605-management", "605-legacy"]
# use our logger, the formatter is nicer than sceptre
LOGGER = util.get_logger("resolvers." + __name__)


class lookup_ami(Resolver):
    session_cache = {}

    def __init__(self, *args, **kwargs):
        super(lookup_ami, self).__init__(*args, **kwargs)

    def filters(self, account_id):
        filters = [
            {"Name": "owner-id", "Values": [str(account_id)]},
            {"Name": "state", "Values": ["available"]},
            {"Name": "image-type", "Values": ["machine"]},
        ]
        for tag in self.image_tags:
            filter_key = tag.split("=")[0]
            filter_val = tag.split("=")[1]
            filter_val = os.path.expandvars(filter_val)
            filters.append(
                {"Name": "tag:%s" % filter_key, "Values": ["%s" % filter_val]}
            )
        LOGGER.info("{}: AMI filters: {}".format(__name__, filters))
        return filters

    def image_compare_by_date(self, first_image, second_image):
        if parser.parse(first_image["CreationDate"]) > parser.parse(
            second_image["CreationDate"]
        ):
            return first_image
        else:
            return second_image

    def client(self, profile):
        """give back an EC2 client to run our AMI query against"""
        session = boto3.session.Session(
            region_name=self.stack.region, profile_name=profile
        )
        return session.client("ec2")

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
            ami_id_candidate_from_environ = self.try_extract_from_environ()
            if ami_id_candidate_from_environ:
                LOGGER.info(
                    "Found AMI ID candidate from environ: {}".format(
                        ami_id_candidate_from_environ
                    )
                )
                return ami_id_candidate_from_environ
            LOGGER.info("No AMI ID configured via environ")
            self.image_tags = self.extract_ami_tags_from_argument()
        except ValueError:
            raise ValueError(
                "Bad syntax for the !lookup_ami "
                " resolver. Use it like this: "
                "'!lookup_ami "
                "Role=analytics-workstation,Name=605-analytics-workstation'"
                " or '!lookup_ami "
                "AMIEnvVar=AMI_ID Project=analytics-workstation,Name=605-analytics-workstation'"
            )
        LOGGER.info(
            "{}: filtering with these tags: {}".format(
                __name__, self.image_tags)
        )
        # We make call using one of AWS_PROFILEs and quering AMIs owned by AWS_PROFILE
        # this way we can see tags created in image baking process
        # If we would extend AWS profiles list, we should refactor sections to loops.
        # since possible scenario of checking only current/management account for AMI
        from botocore.exceptions import ClientError

        try:
            # only works for devops
            response_mngmnt = self.client(AWS_PROFILE[0]).describe_images(
                Filters=self.filters(AWS_ACCOUNT_ID[0])
            )
        except ClientError as exc:
            LOGGER.info(
                "{}: error querying management occurred (this is normal for most users) {}".format(
                    __name__, exc
                )
            )
            response_mngmnt = dict(Images=[])
        response_legacy = self.client(AWS_PROFILE[1]).describe_images(
            Filters=self.filters(AWS_ACCOUNT_ID[1])
        )
        # We sort responses and log info on query results.
        list_of_images_mngmnt = sorted(
            response_mngmnt["Images"], key=lambda img: img["CreationDate"]
        )
        LOGGER.info(
            "{}: found matches {} on management account".format(
                __name__, list_of_images_mngmnt
            )
        )
        list_of_images_legacy = sorted(
            response_legacy["Images"], key=lambda img: img["CreationDate"]
        )
        LOGGER.info(
            "{}: found matches {} on legacy account".format(
                __name__, list_of_images_legacy
            )
        )

        # If tree to check and return latest image based on data from both accounts
        if not (list_of_images_legacy or list_of_images_mngmnt):
            raise ValueError(
                "query on legacy and management account returns no AMIs! Filters:\n{}\n{}".format(
                    self.filters(AWS_ACCOUNT_ID[0]), self.filters(
                        AWS_ACCOUNT_ID[1])
                )
            )
        elif not list_of_images_legacy:
            latest = list_of_images_mngmnt[-1]
        elif not list_of_images_mngmnt:
            latest = list_of_images_legacy[-1]
        else:
            latest = self.image_compare_by_date(
                list_of_images_mngmnt[-1], list_of_images_legacy[-1]
            )

        LOGGER.info("{}: most recent match {}".format(
            __name__, latest["ImageId"]))
        return latest["ImageId"]

    def try_extract_from_environ(self):
        arguments = self.argument.split()
        if len(arguments) > 1:
            for argument in arguments:
                split_values = argument.split("=")
                if split_values[0] == "AMIEnvVar":
                    return os.environ.get(split_values[1])
        return None

    def extract_ami_tags_from_argument(self):
        arguments = self.argument.split()
        if (
            len(arguments) == 1
        ):  # case when only AMI tags are provided without AMIEnvVar provided
            return arguments[0].split(",")
        for argument in arguments:
            split_values = argument.split("=")
            if split_values[0] != "AMIEnvVar":
                return argument.split(",")
