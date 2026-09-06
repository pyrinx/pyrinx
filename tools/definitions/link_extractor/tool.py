"""Link extractor tool — extracts URLs from HTTP response bodies by HTML tag."""

from __future__ import annotations

from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from core.agent_context import AppContext
from database.repository import get_exchange_body
from tools.policy.categories import ToolCategory
from tools.policy.tags import what, when, where, who
from tools.registry.types import ToolDef

from .schema import SCHEMA

_TAG_ATTRIBUTE: dict[str, str] = {
    "a": "href",
    "audio": "src",
    "iframe": "src",
    "img": "src",
    "link": "href",
    "script": "src",
    "source": "src",
    "video": "src",
}

_DEFAULT_TAGS: list[str] = ["a"]

ExchangeResult = dict[str, list[str] | str]


def _extract_links_from_html(
    html: str, base_url: str, tags: list[str]
) -> ExchangeResult:
    unsupported = [tag for tag in tags if tag not in _TAG_ATTRIBUTE]
    if unsupported:
        supported = ", ".join(sorted(_TAG_ATTRIBUTE))
        return {
            "error": f"unsupported tags: {', '.join(unsupported)}. Supported: {supported}."
        }

    tree = HTMLParser(html)
    extracted_links: list[str] = []
    found_tags: set[str] = set()

    for tag in tags:
        attribute = _TAG_ATTRIBUTE.get(tag)
        if not attribute:
            continue

        nodes = tree.css(tag)
        if nodes:
            found_tags.add(tag)

        for node in nodes:
            raw_value = node.attributes.get(attribute)
            if not raw_value:
                continue

            url = urljoin(base_url, raw_value) if base_url else raw_value
            extracted_links.append(url)

    missing_tags = [tag for tag in tags if tag not in found_tags]

    if not extracted_links:
        error_tags = ", ".join(missing_tags or tags)
        reason = "tags not found" if missing_tags else "no links found for tags"
        return {"error": f"{reason}: {error_tags}"}

    if missing_tags:
        return {
            "links": extracted_links,
            "warning": f"tags not found: {', '.join(missing_tags)}",
        }

    return {"links": extracted_links}


def extract_links_by_exchange(
    ids: list[str],
    tags: list[str] | None = None,
) -> dict[str, ExchangeResult]:
    """Extract absolute URLs from response bodies for the given exchange IDs.

    Fetches response bodies, parses them as HTML, extracts links from the given
    tags, and resolves relative URLs against each exchange's base URL.

    Args:
        ids: Exchange IDs to process. Must be non-empty.
        tags: HTML tags to extract links from. Defaults to ``["a"]``.
            Valid values are the keys of ``_TAG_ATTRIBUTE``.

    Returns:
        Dict mapping each exchange ID to one of:

        - ``{"links": [...]}`` — extracted URLs.
        - ``{"links": [...], "warning": "..."}`` — extracted URLs; some tags absent.
        - ``{"error": "..."}`` — extraction failed for this exchange.

    Raises:
        ValueError: If ``ids`` is empty.
    """
    if not ids:
        raise ValueError("ids must be a non-empty list")

    resolved_tags = tags if tags is not None else _DEFAULT_TAGS
    exchanges = get_exchange_body(ids)
    results: dict[str, ExchangeResult] = {}

    for exchange in exchanges:
        exchange_id: str = exchange.get("id", "")

        if "error" in exchange:
            results[exchange_id] = {"error": exchange["error"]}
            continue

        html: str = exchange.get("response_body", "")
        base_url: str = exchange.get("url", "")

        if not html:
            results[exchange_id] = {"error": "response body is empty"}
            continue

        results[exchange_id] = _extract_links_from_html(html, base_url, resolved_tags)

    return results


def handle(
    arguments: dict[str, object], ctx: AppContext
) -> dict[str, ExchangeResult | str]:
    """Registry dispatch handler for this tool.

    Args:
        arguments: Tool arguments (``ids``, optional ``tags``).
        ctx: Application context (unused; required by registry contract).

    Returns:
        Dict mapping exchange IDs to results, or an error dict on validation failure.
    """
    try:
        return extract_links_by_exchange(**arguments)  # type: ignore[arg-type]
    except ValueError as exc:
        return {"error": str(exc), "type": "ValidationError"}


TOOL = ToolDef(
    name="link_extractor",
    description="Extract links from response bodies of given exchange IDs by HTML tags.",
    category=ToolCategory.ANALYSIS,
    tags=[what.extraction, who.html, when.response, where.body],
    parameters=SCHEMA,
    handler=handle,
)
