"""JSON schema for link_extractor tool parameters."""

SCHEMA = {
    "type": "object",
    "properties": {
        "ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Exchange IDs to extract links from.",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["a"],
            "description": (
                "HTML tags to extract "
                "(a, script, img, iframe, link, source, video, audio)."
            ),
        },
    },
    "required": ["ids"],
    "additionalProperties": False,
}
