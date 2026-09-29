"""Actionable errors shared by every cryptodl entry point."""

from __future__ import annotations


class CryptoDLError(Exception):
    """An error with a human- and agent-readable message plus optional suggestions.

    `suggestions` is a list of short strings (e.g. close symbol matches) that gets
    folded into the message and, in --json mode, exposed as a separate field.
    """

    def __init__(self, message: str, suggestions: list[str] | None = None) -> None:
        self.message = message
        self.suggestions = suggestions or []
        full = message
        if self.suggestions:
            full = f"{message} Suggestions: {', '.join(self.suggestions)}"
        super().__init__(full)

    def to_dict(self) -> dict:
        return {"error": self.message, "suggestions": self.suggestions}
