"""Core implementation for Local Snapshotter Context.

The library captures a context-local dict of key-value pairs and returns a
serialized token string suitable for propagation across process boundaries.
The serialization format is intentionally compact and deterministic.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Mapping, Optional


class SnapshotContext:
    """Context-local holder for key-value pairs.

    The context stores a single flat mapping. Keys must be strings, values
    must be JSON-serializable. This restriction keeps the serialized token
    portable and predictable across process boundaries.
    """

    def __init__(self, initial: Optional[Mapping[str, Any]] = None) -> None:
        """Create a new snapshot context.

        Args:
            initial: Optional initial key-value mapping. If not provided,
                the context starts empty. The mapping is shallow-copied so
                later changes to the argument do not affect this context.

        Raises:
            TypeError: If any key is not a string, or if any value is not
                JSON-serializable.
            ValueError: If the initial mapping contains duplicate keys after
                JSON round-trip. This cannot normally happen with a dict, but
                custom mappings may expose surprising key semantics; we guard
                against it to keep tokens deterministic.
        """
        self._data: Dict[str, Any] = {}
        if initial is not None:
            self.update(initial)

    def update(self, values: Mapping[str, Any]) -> None:
        """Merge key-value pairs into the context.

        Existing keys are overwritten. The mapping is copied before
        serialization so that later mutations to the argument do not alter
        this context.

        Args:
            values: Mapping of string keys to JSON-serializable values.

        Raises:
            TypeError: If any key is not a string, or if any value is not
                JSON-serializable.
            ValueError: If the resulting context would contain non-string keys
                after JSON round-trip. This is a defensive check; plain dicts
                with string keys always pass.
        """
        candidate = dict(values)
        for key in candidate:
            if not isinstance(key, str):
                raise TypeError(f"Keys must be strings, got {type(key).__name__}")
        # Validate serializability and key stability by round-tripping through
        # JSON. This is deliberately strict: we want to fail at update time,
        # not when the token is requested.
        encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
        decoded = json.loads(encoded)
        if set(decoded.keys()) != set(candidate.keys()):
            raise ValueError("Context keys are not stable after JSON serialization")
        self._data.update(candidate)

    def remove(self, key: str) -> None:
        """Remove a key from the context.

        Args:
            key: Key to remove. If the key does not exist, this is a no-op.

        Raises:
            TypeError: If the key is not a string.
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string, got {type(key).__name__}")
        self._data.pop(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for a key, or a default.

        Args:
            key: Key to look up.
            default: Value returned if the key is missing. Defaults to None.

        Raises:
            TypeError: If the key is not a string.
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string, got {type(key).__name__}")
        return self._data.get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        """Return a shallow copy of the context as a dict."""
        return dict(self._data)

    def clear(self) -> None:
        """Remove all key-value pairs."""
        self._data.clear()

    def to_token(self) -> str:
        """Serialize the context to a portable token string.

        The token is deterministic for a given context: keys are sorted and
        the JSON payload is base64-encoded. The token contains no characters
        that require URL escaping.

        Returns:
            A string token. Empty contexts return the token for an empty
            JSON object, which is still a valid token.
        """
        return encode_snapshot(self._data)

    @classmethod
    def from_token(cls, token: str) -> "SnapshotContext":
        """Create a context from a previously generated token.

        Args:
            token: Token produced by to_token or encode_snapshot.

        Returns:
            A new SnapshotContext containing the deserialized data.

        Raises:
            ValueError: If the token is malformed or does not decode to a
                JSON object with string keys.
        """
        data = decode_snapshot(token)
        return cls(data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SnapshotContext):
            return NotImplemented
        return self._data == other._data

    def __repr__(self) -> str:
        return f"SnapshotContext({self._data!r})"


def encode_snapshot(data: Mapping[str, Any]) -> str:
    """Encode a mapping to a deterministic token string.

    Keys are sorted before serialization so that two mappings with the same
    entries always produce the same token, regardless of insertion order.
    The JSON payload is base64-encoded using URL-safe alphabet without
    padding to keep the token safe for use in environment variables, headers,
    and command-line arguments.

    Args:
        data: Mapping of string keys to JSON-serializable values.

    Returns:
        A string token.

    Raises:
        TypeError: If data contains non-string keys or non-serializable values.
        ValueError: If the mapping contains keys that are not stable after
            JSON round-trip.
    """
    # Validate keys up front so we fail before encoding.
    for key in data:
        if not isinstance(key, str):
            raise TypeError(f"Keys must be strings, got {type(key).__name__}")
    try:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Context values must be JSON-serializable: {exc}") from exc

    # Defensive round-trip check. A plain dict always passes, but this makes
    # the behaviour explicit and future-proof if custom mappings are used.
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("Serialized context must decode to a JSON object")
    if set(decoded.keys()) != set(data.keys()):
        raise ValueError("Context keys are not stable after JSON serialization")

    encoded_bytes = payload.encode("utf-8")
    token = base64.urlsafe_b64encode(encoded_bytes).decode("ascii").rstrip("=")
    return token


def decode_snapshot(token: str) -> Dict[str, Any]:
    """Decode a token string back to a mapping.

    The token is expected to be a URL-safe base64 encoding of a UTF-8 JSON
    object. Padding is optional and added back before decoding. Whitespace in
    the token is ignored to tolerate accidental line wrapping.

    Args:
        token: Token produced by encode_snapshot or SnapshotContext.to_token.

    Returns:
        A dict with string keys and JSON-decoded values.

    Raises:
        ValueError: If the token is not valid base64, is not valid UTF-8, or
            does not decode to a JSON object.
        TypeError: If the token is not a string.
    """
    if not isinstance(token, str):
        raise TypeError(f"Token must be a string, got {type(token).__name__}")

    # Remove whitespace and restore padding. URL-safe base64 requires length
    # to be a multiple of 4 after padding.
    cleaned = "".join(token.split())
    if not cleaned:
        raise ValueError("Token must not be empty")
    padding = "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(cleaned + padding)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(f"Token is not valid base64: {exc}") from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Token payload is not valid UTF-8") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Token payload is not valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("Token payload must decode to a JSON object")
    for key in data:
        if not isinstance(key, str):
            raise ValueError("Token payload object must have string keys")
    return data
