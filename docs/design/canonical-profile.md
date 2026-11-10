# Canonical proposal profile `c1`

Author: Mohammed Alsaleh · Status: IMPLEMENTED and TESTED, awaiting independent review (ticket SB-012, decision PD-004) · Requirements CR-31, CR-33

An approval is bound to a hash. The hash is only meaningful if a proposal has exactly one byte representation, so the rule throughout is: **a payload either has one canonical form or it is rejected. Nothing is coerced, and nothing is dropped silently.** The implementation is `src/second_brain/domain/canonical.py`; the test vectors are `tests/unit/test_canonical.py`.

## 1. What a payload may contain

| Item | Rule | Rejected examples |
|---|---|---|
| Payload | A JSON object | An array, a string, a number at the top level |
| Values | Object, array, string, integer, `true`, `false`, `null` | Floats, `NaN`, `Infinity`, bytes, sets, tuples, dates, enumerations, any subclass of a permitted type |
| Integers | Within ±(2^53 − 1), the range every JSON parser reads exactly | `9007199254740992`; larger numbers and all decimals travel as strings |
| Strings | Normalised to Unicode NFC | A surrogate code point; a Unicode noncharacter |
| Object keys | Non-empty strings, normalised to NFC, free of control, format, surrogate, private-use and unassigned characters | `""`, a key holding a zero-width space or a direction override |
| Key uniqueness | No two keys of one object may be equal after NFC | `café` written once precomposed and once with a combining accent |
| Nesting | At most 32 levels | Deeper structures; self-referencing structures |

Key collisions are checked while the canonical object is being built, key by key, so the error is raised before any value could replace another.

## 2. The bytes

`{"payload": <canonical payload>, "v": "c1"}` serialised as UTF-8 JSON with no insignificant whitespace, object keys sorted by Unicode code point, non-ASCII characters written literally, and the standard JSON escapes for `"`, `\` and characters below U+0020. The proposal hash is the SHA-256 of those bytes, in lowercase hexadecimal.

The version is inside the hashed bytes. A change to any rule on this page is a new version (`c2`), never an edit to `c1`; golden vectors in the tests fail if the output for `c1` changes.

## 3. Received text

`parse_proposal_json` is the only supported way to turn received text into a payload. In addition to the rules above it rejects, at any depth:

- duplicate keys, including keys that differ only by escaping (`"a"` and `"a"`), which the standard parser accepts by silently keeping the last value;
- numbers with a fraction or exponent, `NaN`, `Infinity`;
- invalid UTF-8, a byte-order mark, trailing data, anything that is not strict JSON.

## 4. Batches

A batch digest is the SHA-256 of `batch:c1`, a line feed, and the member hashes joined by line feeds. Every member must be a 64-character lowercase hexadecimal digest and may appear once. Order and membership both change the digest.

## 5. Obligations on the code that uses this module

These are not enforced here and must be met, and tested, where the proposal engine and approval surface are built (SB-048, SB-058, SB-059, SB-060):

1. What is shown to the owner, hashed, stored and applied is the output of `canonical_payload`, never the text as received.
2. The hash is recomputed from the stored canonical payload at approval and again at apply; a stored hash is never trusted on its own.
3. The schema of each proposal kind (which fields are required, which values are allowed) is validated separately. This profile guarantees one representation, not a valid proposal.
4. NFC is the only normalisation of values. Look-alike characters, compatibility forms and direction-changing characters inside string values are distinct here by design; the approval surface must make them visible (SB-059).

## 6. Known limits

- Key order follows Unicode code points, not the UTF-16 order of RFC 8785; the profile is self-contained and does not claim to be RFC 8785.
- No independent implementation has yet reproduced the vectors, and no reviewer other than the author has examined the module.
