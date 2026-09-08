"""Tag policy — three namespaces used to classify tools.

    ACTION  what the tool does           (required, exactly one)
    FOR     what it targets              (optional)
    FROM    where its data comes from    (optional)

A tool always needs its ACTION plus at least one of FOR / FROM, so every
tool carries 2 or 3 tags in total. Tags are plain strings — no wrapper
object, no namespace metadata attached to the value itself.

Usage::

    from tools.policy.tags import ACTION, FOR, FROM

    tags = [ACTION.extract, FOR.link, FROM.html]
    tags = [ACTION.request, FOR.http]
    tags = [ACTION.execute, FOR.command]

Note: member values are unique *across* the three classes below. That is
what lets the validator figure out which namespace a plain string tag
belongs to without needing a wrapper object.
"""

from __future__ import annotations


class _Action:
    """What the tool does."""

    extract = "extract"
    request = "request"


class _For:
    """What the tool targets."""

    http = "http"
    link = "link"


class _From:
    """Where the tool's data comes from."""

    html = "html"
    ftp = "ftp"


ACTION = _Action()
FOR = _For()
FROM = _From()
