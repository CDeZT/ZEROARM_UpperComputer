"""Stable application error hierarchy."""


class ZeroArmError(Exception):
    """Base class for errors safe to classify across application layers."""


class ProtocolDecodeError(ZeroArmError):
    """A valid outer frame contains an invalid V1 command payload."""
