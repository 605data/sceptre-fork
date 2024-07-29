# -*- coding: utf-8 -*-
"""
A sceptre resolver that given sceptre config yaml like this:

```
    my_policy: !policy some-policy.json
```

Will give back the minified contents of the file at `$SCEPTRE_ROOT/policies/some-policy.json`.
If you pass a filename ending in .j2, it will render the json before minification.
"""

from __future__ import absolute_import
from __future__ import division

import imp
import glob
import json
import os

import demjson3
from devops import (
    util,
)
from sceptre.resolvers import Resolver
from sceptre.template import Template

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    # UndefinedError,
)

from pygments import highlight, lexers, formatters

PYGMENTS_LEXER = lexers.JsonLexer()
PYGMENTS_FORMATTER = formatters.Terminal256Formatter(style="algol")

FIRST_INIT = True
SCEPTRE_DIR = os.environ["SCEPTRE_ROOT"]
POLICY_DIR = os.path.join(SCEPTRE_DIR, "policies")
VALIDATE = os.environ.get("SCEPTRE_VALIDATE_PRINCIPALS", False)
DEFAULT_POLICY_LENGTH_LIMIT = 10240.0

# use our  logger, the formatter is nicer than sceptre
LOGGER = util.get_logger("resolvers." + __name__)

# quiet logs if running from atlantis
if os.environ.get("ATLANTIS_LOG_LEVEL"):
    LOGGER.info = lambda *args, **kwargs: None
    LOGGER.debug = lambda *args, **kwargs: None


def get_jinja_filters():
    """
    Returns cached jinja filters if already computed, or loads/caches
    the filters from python files if this is the first time.

    This (optional) feature relies on the environment variable
    ${SCEPTRE_JINJA_FILTER_ROOT} because we don't have easy access
    from here to CLI parsing info or global configuration info.
    """

    # give back cached jinja filters if available
    if hasattr(get_jinja_filters, "_jinja_filters"):
        return get_jinja_filters._jinja_filters
    # load jinja filters if not already cached
    env_var_name = "SCEPTRE_JINJA_FILTER_ROOT"
    if env_var_name not in os.environ:
        msg = "${} is not set, no extra jinja filters will be loaded"
        LOGGER.debug(msg.format(env_var_name))
        get_jinja_filters._jinja_filters = {}
        return get_jinja_filters._jinja_filters
    else:
        filter_dir = os.environ[env_var_name]
        if not os.path.exists(filter_dir):
            err = "${} is set, but directory does not exist!"
            raise ValueError(err.format(env_var_name))
        else:
            msg = "loading jinja filters from: {}"
            LOGGER.debug(msg.format(filter_dir))
            get_jinja_filters._jinja_filters = {}
            for fpath in glob.glob(os.path.join(filter_dir, "*.py")):
                LOGGER.debug("  loading filter: {}".format(fpath))
                mod = imp.load_source("dynamic_jinja_filters", fpath)
                for name in dir(mod):
                    # ignore anything like private methods
                    if name.startswith("_"):
                        continue
                    else:
                        fxn = getattr(mod, name)
                        # ignore things that aren't callables
                        if callable(fxn):
                            get_jinja_filters._jinja_filters[name] = fxn
            return get_jinja_filters._jinja_filters


def shortpath(path):
    """FIXME: move to devops.util"""
    return (os.environ.get("HOME") and path.replace(os.environ["HOME"], "~")) or path


class policy(Resolver):
    """
    Resolver for the contents of a file.
    :param argument: Absolute path to file.
    :type argument: str
    """

    def __init__(self, *args, **kwargs):
        super(policy, self).__init__(*args, **kwargs)
        if not os.path.exists(POLICY_DIR):
            err = "missing policy directory: " + POLICY_DIR
            raise RuntimeError(err)
        self.policy_root = POLICY_DIR
        # we use FileSystemLoader so that templates may use {% include %}
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.policy_root), undefined=StrictUndefined
        )
        # allow the !policy decorator to support the same
        # jinja filters  that the rest of sceptre supports
        tmp = Template("junk data, we just need a object", {})
        self.jinja_env.filters.update(get_jinja_filters())
        # FIXME: avoid this hack with __new__?
        global FIRST_INIT
        if FIRST_INIT:
            LOGGER.info("initializing")
            LOGGER.info(
                "  policy_root for lookups is: {}".format(self.policy_root))
            FIRST_INIT = False

    @property
    def path(self):
        """retrieves the path element that was
        used with this !policy constructor
        """
        path = self.argument.split().pop(0)
        path = os.path.join(self.policy_root, path)
        err = "missing policy file: {0}".format(path)
        assert os.path.exists(path), err
        file_checks = [path.endswith(".j2"), path.endswith(".json")]
        if not any(file_checks):
            raise SystemExit("path should end in .json or .j2")
        return path

    @property
    def local_vars(self):
        """retrieves the (optional) local variables
        that were used with !policy constructor
        """
        args = self.argument.split()
        args.pop(0)  # policy path, not interested in that

        if not args:
            return {}  # local vars are optional, in this case not provided

        # otherwise, parse a string like `k1=v1,k2=v2,..` into vars dict
        _vars_list = " ".join(args).split(",")
        _vars_list = [x.strip() for x in _vars_list if x.strip()]
        try:
            _vars = dict([x.split("=") for x in _vars_list])
        except ValueError:
            err = (
                "Syntax for !policy is either simply `!policy policy_file`"
                " or `!policy policy_file key=val,k2=v2,..`"
                " but this value cannot be parsed: {0}"
            ).format(str(args))
            raise ValueError(err)
        else:
            msg = str(_vars)
            if len(msg) > 50:
                msg = json.dumps(_vars, indent=2).replace("\n", "\n\t")
            msg = "vars = \n\t{}".format(msg)
            LOGGER.info(msg)
            return _vars

    def resolve(self):
        return self.r(self.path, self.stack, self.local_vars, self.jinja_env)

    @staticmethod
    def r(path, stack, local_vars, jinja_env):
        """get the policy file from `policy_root`, and return it,
        rendering it with the standard context if applicable
        """
        context = (
            {}
        )  # might stay empty if we're not actually rendering (i.e. if no .j2)
        with open(path, "r") as fhandle:
            policy_content = fhandle.read()
        if path.endswith(".j2"):
            LOGGER.info("rendering: {}".format(shortpath(path)))
            # we render policy content with a context where
            # stack-config overrides environment-config overrides
            # any local variables so that policies themselves may
            # be templated, and we can support jinja comments/filters
            # in otherwise normal json
            context = stack.stack_group_config.copy()
            context.update(
                vars=local_vars,
                # sceptre_user_data=stack.sceptre_user_data,
                sceptre_user_data=stack.__dict__["__sceptre_user_data"],
            )
            policy_content = jinja_env.from_string(
                policy_content).render(**context)

        # we determine policy length limits based on some hints,
        # because aws supports different lengths depending on
        # whether this is a trust-policy, a bucket-policy, or a
        # plain old iam policy.
        if (
            "sceptre_user_data" in context
            and "private_buckets" in context["sceptre_user_data"]
        ):
            policy_char_limit = 20480.0
        # FIXME: elif ... this is an assume-role-policy-document policy
        else:
            policy_char_limit = DEFAULT_POLICY_LENGTH_LIMIT

        # minify policy before we return it.  use demjson3 here
        # so we can tolerate json with trailing commas, etc
        try:
            policy_content = demjson3.decode(policy_content)
        except (ValueError, demjson3.JSONDecodeError) as exc:
            err = "{}\n\nCannot load policy content: {}"
            raise ValueError(err.format(exc, policy_content))

        # maybe validate policy principals.  this is heuristic,
        # but still useful because errors in this can be hard to
        # track down.. i.e. one bad user ARN out of dozens or huundreds
        if VALIDATE:
            from devops.abcs.policy import Policy

            policy = Policy(policy_content)
            policy.validate()

        log_chan = LOGGER.info
        result = json.dumps(policy_content)
        msg = highlight(
            json.dumps(policy_content,
                       indent=2), PYGMENTS_LEXER, PYGMENTS_FORMATTER
        )

        # show (rendered) policy on default log channel
        log_chan("{}".format(msg))

        # detect policies over or nearly over threshhold,
        # changing log channel to notify if necessary
        policy_length = len(result.encode("utf-8"))
        percent = (policy_length / policy_char_limit) * 100
        warn_thresh, crit_thresh = 30, 80  # threshholds for logging output

        def color_fxn(x):
            return x

        if percent > warn_thresh:
            log_chan = LOGGER.warning
            color_fxn = util.blue  # noqa
        if percent > crit_thresh:
            log_chan = LOGGER.critical
            color_fxn = util.red  # noqa
            if percent > 100:
                log_chan = LOGGER.error
                log_chan(
                    "policy too long, this will probably"
                    "break if update is attempted!"
                )
        percent = color_fxn("{}%".format(percent))
        msg = "policy renders to {} bytes, {} of the hard limit at {}".format(
            policy_length, percent, policy_char_limit
        )
        msg = highlight(
            msg, lexers.PythonLexer(), formatters.Terminal256Formatter(style="native")
        )
        log_chan(msg.strip())

        # give back the rendered, minified policy, usually so
        # that it may then be inlined into cloudformation templates
        return result
