# Synthetic repository fixture

The two directories are immutable source inputs for Understory's importer and
evaluation. They are not the application backend and must never be installed or
executed by the importer. `understory/fixture` is a synthetic connector identity,
not a claim about a real GitHub repository. Refs `a`/`main` and `b` resolve to
deterministic SHA-1 content identities labeled synthetic in API coverage.

Snapshot B changes validation/tests, adds limits configuration, removes the
legacy module, and renames formatting helpers. Other input bytes are unchanged
so embedding reuse and retained A answers can be verified.

Unsafe archives, binary/encoding edge cases and secret-path samples are built
in tests from inert bytes; they contain no real credentials.
