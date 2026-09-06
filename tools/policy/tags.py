# tools/policy/tags.py
"""W4 tag policy — namespace definitions and tag type.

Defines the four descriptive namespaces (what, who, when, where) used to
classify tools. Each namespace answers a specific question about a tool and
exposes a fixed set of valid members.

Usage::

    from tools.policy.tags import what, who, when, where

    tags = [what.extraction, who.html, when.response, where.body]

Rules:
- A maximum of four tags per tool (one ceiling per namespace).
- No namespace may appear more than once.
- Only pre-defined namespace members are valid.
- All four namespaces are optional; use only what applies.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tag type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Tag:
    """A single classified tag produced by a namespace.

    Attributes:
        namespace: The W4 namespace this tag belongs to (``what``, ``who``,
            ``when``, or ``where``).
        value: The tag value — the answer to the namespace's question.
    """

    namespace: str
    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.namespace}.{self.value}"


# ---------------------------------------------------------------------------
# Question template
# ---------------------------------------------------------------------------

# The universal questions every namespace must be able to answer.
# These serve as the authoring rule when defining new namespace members.
NAMESPACE_QUESTIONS: dict[str, str] = {
    "what": "What is the purpose of this tool?",
    "who": "Who or what provides the data?",
    "when": "When is the data available?",
    "where": "Where is the data located?",
}


# ---------------------------------------------------------------------------
# Namespace base
# ---------------------------------------------------------------------------


class _NamespaceMeta(type):
    """Metaclass that wires Tag instances to their enclosing namespace.

    At class-creation time, scans every string attribute declared on the
    body and promotes it to a ``Tag(namespace=_name, value=<string>)``.
    This removes the need to repeat the namespace name on every member.

    Subclasses only need to declare:

    - ``_name``: the namespace identifier (``"what"``, ``"who"``, etc.).
    - Member attributes as plain strings (the tag values).

    ``_question`` is resolved automatically from ``NAMESPACE_QUESTIONS``.
    """

    def __new__(
        mcs,
        class_name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
    ) -> _NamespaceMeta:
        name: str = namespace.get("_name", "")  # type: ignore[assignment]

        if name:
            # Promote plain string members to Tag instances.
            for attr, value in list(namespace.items()):
                if not attr.startswith("_") and isinstance(value, str):
                    namespace[attr] = Tag(name, value)

            # Resolve the question from the central template — no duplication.
            namespace.setdefault("_question", NAMESPACE_QUESTIONS.get(name, ""))

        return super().__new__(mcs, class_name, bases, namespace)


class _Namespace(metaclass=_NamespaceMeta):
    """Base class for a W4 tag namespace.

    Subclasses declare ``_name`` and list members as plain strings.
    The metaclass promotes each string to a ``Tag`` and resolves
    ``_question`` automatically.

    Accessing an undefined attribute raises ``AttributeError`` with a
    message listing the valid members.
    """

    _name: str
    _question: str

    def __getattr__(self, member: str) -> Tag:
        raise AttributeError(
            f"'{member}' is not a defined member of the '{self._name}' namespace. "
            f'Question: "{self._question}". '
            f"Defined members: {self._defined_members()}."
        )

    def _defined_members(self) -> list[str]:
        return [
            key
            for key, value in vars(type(self)).items()
            if isinstance(value, Tag) and not key.startswith("_")
        ]


# ---------------------------------------------------------------------------
# Namespace definitions
# ---------------------------------------------------------------------------


class _What(_Namespace):
    """Answers: "What is the purpose of this tool?"

    Members describe the primary operation a tool performs.
    """

    _name = "what"

    extraction = "extraction"  # Extracts structured data from a source.
    request = "request"  # Issues an outbound request.
    encoding = "encoding"  # Encodes data into a target format.
    decoding = "decoding"  # Decodes data from an encoded format.
    snippet = "snippet"  # Retrieves a partial segment of data.
    inspection = "inspection"  # Reads and reports metadata or headers.


class _Who(_Namespace):
    """Answers: "Who or what provides the data?"

    Members describe the data source or protocol layer.
    """

    _name = "who"

    http = "http"  # Data comes from an HTTP exchange.
    html = "html"  # Data is parsed from an HTML document.
    header = "header"  # Data comes from HTTP headers.
    body = "body"  # Data comes from the response/request body.
    codec = "codec"  # Data is processed by an encoder/decoder.


class _When(_Namespace):
    """Answers: "When is the data available?"

    Members describe the lifecycle moment when data can be accessed.
    """

    _name = "when"

    response = "response"  # Data is available after a response is received.
    request = "request"  # Data is available at request time.
    on_demand = "on_demand"  # Data is produced when the tool is invoked.


class _Where(_Namespace):
    """Answers: "Where is the data located?"

    Members describe the physical or logical location of the data.
    """

    _name = "where"

    body = "body"  # Data resides in the message body.
    header = "header"  # Data resides in HTTP headers.
    url = "url"  # Data resides in the URL.
    document = "document"  # Data resides in a parsed document structure.


# ---------------------------------------------------------------------------
# Public namespace instances
# ---------------------------------------------------------------------------

what = _What()
who = _Who()
when = _When()
where = _Where()
