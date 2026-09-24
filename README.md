# Local Snapshotter Context

Local Snapshotter Context captures a context-local dict of key-value pairs and returns a serialized token string suitable for propagation across process boundaries.

## Usage

```python
from local_snapshotter_context import SnapshotContext, encode_snapshot, decode_snapshot

ctx = SnapshotContext({"request_id": "abc-123", "user": "alice"})
ctx.update({"region": "eu-west"})

token = ctx.to_token()
# Pass token to another process, for example as an environment variable.

restored = SnapshotContext.from_token(token)
print(restored.as_dict())
# {'request_id': 'abc-123', 'user': 'alice', 'region': 'eu-west'}
```

You can also work with the module-level functions directly:

```python
from local_snapshotter_context import encode_snapshot, decode_snapshot

token = encode_snapshot({"a": 1, "b": [1, 2, 3]})
data = decode_snapshot(token)
```

## Why this library exists

Passing structured context between processes usually means either sharing a mutable store or inventing an ad-hoc serialization format. This library provides a deliberately small, deterministic token format for a flat JSON-serializable mapping. The trade-off is that values must be JSON-serializable: tuples are not supported, custom objects are not supported, and keys must be strings. That restriction is the price for a token that is safe to pass through environment variables, command-line arguments, or HTTP headers without escaping.

## Awkward edge to watch for

The token is base64-encoded URL-safe JSON without padding. When decoding, the library restores padding automatically, so tokens with or without `=` padding are accepted. Empty tokens are rejected, but an empty context still produces a valid non-empty token that decodes back to `{}`. Do not confuse an empty context with an empty token.

Exported names: `SnapshotContext`, `encode_snapshot`, `decode_snapshot`.
