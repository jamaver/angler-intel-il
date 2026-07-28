# V7.3 Legacy Reference Remediation

V7 validation preserves historical catch records even when their original gear
or water reference cannot be resolved to a current normalized record.  It does
not create guessed replacements.

## Current classification

The pre-transition validator can report `unmapped_reference` entries for:

- catch gear IDs whose original owned item no longer exists;
- free-text catch water labels that do not identify a saved/base waterbody;
- any other historical reference lacking a deterministic normalized ID.

The original catch payload and its `gear_labels` snapshot remain intact.  This
is historical evidence, not a reason to fabricate a gear or waterbody link.

## Transition gate

`tools/v7_authority.py preflight` refuses a transition when validation has a
warning status.  Record parity alone is not enough.  An operator must first
resolve a reference, preserve it as an explicitly accepted legacy link through
a future migration policy, or remove only test-generated data through a
reviewed cleanup.

## Operator decisions before a related domain transition

For historical gear references, choose one of:

1. Link the catch to a confirmed existing gear item.
2. Retain the null normalized link and its original label as an accepted legacy
   snapshot, with an operator-recorded reason.

For historical water labels, choose one of:

1. Link the catch to a confirmed waterbody.
2. Retain the original water label without a normalized ID.

Neither choice should be automated from a name similarity match.  Target
profile authority is also held until the global validation gate is explicitly
clear or a later V7.3 policy records these legacy exceptions.

SQLite authority remains `json` during this remediation work.

## Reviewed decision ledger

Use `tools/v7_3_legacy_references.py list --json` to enumerate unresolved
historical references.  A decision must include an operator name and reason:

```bash
./venv/bin/python tools/v7_3_legacy_references.py accept \
  --catch-id CATCH_ID --relationship gear --role rod \
  --reference OLD_GEAR_ID --note "Original rod retired" --operator pi
```

To link a confirmed normalized item instead, use `link` with `--target-id`.
The tool verifies the target exists.  Decisions are tied to the exact canonical
catch payload hash; editing the source catch invalidates the prior decision and
returns it to review.  No command writes JSON or changes authority.
