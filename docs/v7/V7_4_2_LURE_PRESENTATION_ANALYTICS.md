# V7.4.2 Lure And Presentation Analytics

V7.4.2 adds `GET /api/analytics/lures`. The read-only endpoint summarizes
recorded lure and rig or presentation text by species and waterbody, always
with the same bounded sample and confidence labels as the V7.4 query layer.

It reports frequency only. Lure color and lure weight remain explicitly
unavailable because historical catch records do not have normalized fields for
those values. The service does not infer them from free-text lure labels.

Live Smart Intelligence, lure recommendations, and dashboard ranking remain
unchanged. A later UI integration may display these summaries after review.
