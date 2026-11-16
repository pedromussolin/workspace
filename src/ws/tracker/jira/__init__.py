"""Jira implementation of the tracker port: client, ADF, discover and the adapter.

Submodules load inside the functions: `userconfig` reaches `client` through this package, so a
top-level import of `adapter` (which imports `userconfig`) would be an import cycle.
"""


def parse_settings(table, path, section=None):
    """`section` names the table in the messages: `tracker.jira`, or `jira` for the old table."""
    from ws.tracker.jira import settings

    return settings.parse_settings(table, path, section or settings.SECTION)


def open_tracker(config, connection_only=False):
    from ws.tracker.jira import adapter

    return adapter.open_tracker(config, connection_only)


def open_writer(config, entries):
    from ws.tracker.jira import adapter

    return adapter.open_writer(config, entries)


def task_from_listing(card, settings):
    from ws.tracker.jira import adapter

    return adapter.task_from_listing(card, settings)


def card_url_template(settings):
    from ws.tracker.jira import writer

    return writer.card_url_template(settings)


def card_url_template_from_table(table, path, section=None):
    from ws.tracker.jira import settings

    return settings.card_url_template(table, path, section or settings.SECTION)


def __getattr__(name):
    if name == "JIRA_CAPABILITIES":
        from ws.tracker.jira import adapter

        return adapter.JIRA_CAPABILITIES
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
