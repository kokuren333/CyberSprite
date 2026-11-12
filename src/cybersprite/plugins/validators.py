"""Adapt enabled plugin rules to the core's injectable quality-rule provider."""

import re

from cybersprite.core import quality
from cybersprite.core.quality_platform import LEVELS as PLATFORM_LEVELS

from . import PluginManager, as_items, plugin_error


def rules(manager):
    staged = {}
    for descriptor in manager.descriptors("cybersprite.validators"):
        try:
            values = as_items(manager.load(descriptor.group, descriptor.name))
            pending = {}
            for rule in values:
                if not re.fullmatch(r"Q-" + re.escape(descriptor.name) + r"-\d{2,}", rule.rule):
                    raise ValueError("rule ID must be Q-<entry-point-name>-nn")
                if rule.default_severity not in ("error", "warning", "info", "off"):
                    raise ValueError("default_severity must be error, warning, info or off")
                if (
                    not callable(rule.check)
                    or rule.rule in pending
                    or rule.rule in staged
                    or rule.rule in quality.DEFAULT_LEVELS
                    or rule.rule in PLATFORM_LEVELS
                    or rule.rule == "Q-CRF-01"
                ):
                    raise ValueError("rule must have a unique ID and callable check")
                pending[rule.rule] = rule
            staged.update(pending)
        except Exception as error:
            manager.discard(descriptor.group, descriptor.name)
            raise plugin_error(
                descriptor.name, f"validator registration failed: {error}"
            ) from error
    return [staged[key] for key in sorted(staged)]


def configure_validation(manager=None):
    """Install a lazy provider; core does not import discovery or format libraries."""
    manager = manager or PluginManager(groups=("cybersprite.validators",))
    quality.plugin_rule_provider = lambda: rules(manager)
