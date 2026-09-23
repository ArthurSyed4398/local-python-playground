"""Tests for Local Snapshotter Context."""

import unittest

from local_snapshotter_context import SnapshotContext, decode_snapshot, encode_snapshot


class TestSnapshotContext(unittest.TestCase):
    def test_initial_empty(self):
        ctx = SnapshotContext()
        self.assertEqual(ctx.as_dict(), {})

    def test_initial_mapping_is_copied(self):
        original = {"a": 1}
        ctx = SnapshotContext(original)
        original["a"] = 999
        original["b"] = 2
        self.assertEqual(ctx.as_dict(), {"a": 1})

    def test_update_and_get(self):
        ctx = SnapshotContext()
        ctx.update({"x": 10, "y": "hello"})
        self.assertEqual(ctx.get("x"), 10)
        self.assertEqual(ctx.get("y"), "hello")
        self.assertIsNone(ctx.get("missing"))
        self.assertEqual(ctx.get("missing", "fallback"), "fallback")

    def test_update_overwrites_existing(self):
        ctx = SnapshotContext({"k": "old"})
        ctx.update({"k": "new"})
        self.assertEqual(ctx.as_dict(), {"k": "new"})

    def test_remove_existing_key(self):
        ctx = SnapshotContext({"a": 1, "b": 2})
        ctx.remove("a")
        self.assertEqual(ctx.as_dict(), {"b": 2})

    def test_remove_missing_key_is_noop(self):
        ctx = SnapshotContext({"a": 1})
        ctx.remove("missing")
        self.assertEqual(ctx.as_dict(), {"a": 1})

    def test_clear(self):
        ctx = SnapshotContext({"a": 1})
        ctx.clear()
        self.assertEqual(ctx.as_dict(), {})

    def test_non_string_key_raises(self):
        ctx = SnapshotContext()
        with self.assertRaises(TypeError):
            ctx.update({1: "value"})

    def test_non_string_key_in_initial_raises(self):
        with self.assertRaises(TypeError):
            SnapshotContext({1: "value"})

    def test_non_json_serializable_value_raises(self):
        ctx = SnapshotContext()
        with self.assertRaises(TypeError):
            ctx.update({"bad": object()})

    def test_to_token_is_deterministic(self):
        ctx_a = SnapshotContext({"b": 2, "a": 1})
        ctx_b = SnapshotContext({"a": 1, "b": 2})
        self.assertEqual(ctx_a.to_token(), ctx_b.to_token())

    def test_to_token_empty_context(self):
        ctx = SnapshotContext()
        token = ctx.to_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)
        self.assertEqual(decode_snapshot(token), {})

    def test_round_trip_via_token(self):
        original = SnapshotContext({"name": "test", "count": 42, "nested": [1, 2, 3]})
        token = original.to_token()
        restored = SnapshotContext.from_token(token)
        self.assertEqual(restored, original)

    def test_from_token_empty_token_raises(self):
        with self.assertRaises(ValueError):
            SnapshotContext.from_token("")

    def test_from_token_invalid_base64_raises(self):
        with self.assertRaises(ValueError):
            SnapshotContext.from_token("!!!not-base64!!!")

    def test_from_token_valid_base64_invalid_json_raises(self):
        import base64

        bad = base64.urlsafe_b64encode(b"not json").decode("ascii").rstrip("=")
        with self.assertRaises(ValueError):
            SnapshotContext.from_token(bad)

    def test_from_token_json_non_object_raises(self):
        import base64

        bad = base64.urlsafe_b64encode(b"[1,2,3]").decode("ascii").rstrip("=")
        with self.assertRaises(ValueError):
            SnapshotContext.from_token(bad)

    def test_encode_snapshot_rejects_non_string_keys(self):
        with self.assertRaises(TypeError):
            encode_snapshot({1: "value"})

    def test_decode_snapshot_rejects_non_string_token(self):
        with self.assertRaises(TypeError):
            decode_snapshot(12345)

    def test_token_ignores_whitespace(self):
        ctx = SnapshotContext({"a": 1})
        token = ctx.to_token()
        spaced = " ".join(token[i : i + 2] for i in range(0, len(token), 2))
        self.assertEqual(decode_snapshot(spaced), {"a": 1})

    def test_equality(self):
        self.assertEqual(SnapshotContext({"a": 1}), SnapshotContext({"a": 1}))
        self.assertNotEqual(SnapshotContext({"a": 1}), SnapshotContext({"a": 2}))
        self.assertNotEqual(SnapshotContext({"a": 1}), "not a context")


class TestEncodeDecode(unittest.TestCase):
    def test_round_trip_simple(self):
        data = {"hello": "world", "count": 3}
        self.assertEqual(decode_snapshot(encode_snapshot(data)), data)

    def test_round_trip_nested(self):
        data = {"list": [1, 2, {"three": 3}], "bool": True, "null": None}
        self.assertEqual(decode_snapshot(encode_snapshot(data)), data)

    def test_encode_deterministic_key_order(self):
        data_a = {"a": 1, "b": 2}
        data_b = {"b": 2, "a": 1}
        self.assertEqual(encode_snapshot(data_a), encode_snapshot(data_b))

    def test_decode_padded_token(self):
        import base64

        payload = '{"a":1}'.encode("utf-8")
        padded = base64.urlsafe_b64encode(payload).decode("ascii")  # includes =
        self.assertEqual(decode_snapshot(padded), {"a": 1})


if __name__ == "__main__":
    unittest.main()
