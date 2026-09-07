from dataclasses import dataclass


@dataclass(frozen=True)
class AppContext:
    session_id: str
    vuln_class: str
    target: str
