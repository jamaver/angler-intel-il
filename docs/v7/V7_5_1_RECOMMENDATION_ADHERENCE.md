# V7.5.1 Recommendation Adherence

V7.5.1 records the user's direct plan-adherence choice from a V7.5.0 trip
completion against the deterministic saved-report best-bet recommendation.
The association is updated in place for each report and stores whether the
trip occurred, the reported outcome, catch count, satisfaction, and notes.

The feature never infers adherence from catch records. Legacy reports without
a persisted best-bet recommendation still save their trip outcome normally and
return a visible not-linked status. Live Smart Intelligence and ranking remain
unchanged.
