"""Exceptions raised by pyheatlink."""

from __future__ import annotations


class HeatLinkError(Exception):
    """Base class for every pyheatlink error."""


class HeatLinkConnectionError(HeatLinkError):
    """The head could not be reached, timed out, or sent an unreadable reply."""


class HeatLinkResponseError(HeatLinkError):
    """The head answered with an HTTP error status."""

    def __init__(self, status: int, message: str = "") -> None:
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}" if message else f"HTTP {status}")


class HeatLinkAuthError(HeatLinkResponseError):
    """401: the token is missing, wrong or revoked (or a ticket is invalid)."""


class HeatLinkScopeError(HeatLinkResponseError):
    """403: the token is valid but its scope doesn't allow this call."""


class HeatLinkNotFoundError(HeatLinkResponseError):
    """404: unknown endpoint (older firmware) or unknown target."""


class HeatLinkConflictError(HeatLinkResponseError):
    """409: the head refused because of its current state.

    For example: a paired room sensor owns the room temperature, the head is
    not in a group, or an update is already running.
    """


class HeatLinkRateLimitError(HeatLinkResponseError):
    """429: locked out after too many failed attempts."""


class HeatLinkUnsupportedError(HeatLinkError):
    """The head's firmware doesn't advertise the feature this call needs."""
