"""Stable application error hierarchy."""


class ZeroArmError(Exception):
    """Base class for errors safe to classify across application layers."""


class ProtocolDecodeError(ZeroArmError):
    """A valid outer frame contains an invalid V1 command payload."""


class TransportError(ZeroArmError):
    """Base class for byte transport failures."""


class TransportOpenError(TransportError):
    """A transport could not be opened."""


class TransportPermissionError(TransportOpenError):
    """The operating system denied access to a transport."""


class TransportDisconnected(TransportError):
    """The byte link is no longer connected."""


class TransportQueueFull(TransportError):
    """The bounded transport write queue rejected data."""
