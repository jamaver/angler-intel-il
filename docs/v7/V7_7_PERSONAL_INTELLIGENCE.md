# V7.7 Personal Intelligence

V7.7 adds contextual, bounded personal evidence and score explainability. It
does not change live recommendation ranking. Only directly completed trips
with persisted recommendations and `exact` or `partial` adherence qualify.
Did-not-fish, changed-plan, missing-completion, and unlinked records are not
treated as recommendation failures.

Evidence widens from species + waterbody + season + lure to species and then a
global personal baseline. Small samples use a conservative Beta-style prior and
are labeled `none`, `exploratory`, `useful`, or `strong`. The maximum displayed
shadow adjustment remains +/-5 and is not applied.

Species condition profiles use broad, explainable ranges. Forecast trend labels
describe measured changes and are not precise front diagnoses. Component scores
separate fishing-fit estimates from data confidence.

V7.8 is the earliest possible guarded live-personalization milestone and still
requires observed shadow evidence, no unexplained drift, and explicit review.
