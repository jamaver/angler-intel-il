# V7.5.0 Trip Completion

V7.5.0 adds an explicit completion record for each active saved report. A user
can record whether the trip happened, whether the plan was followed, an actual
waterbody and target, a catch count including zero, optional satisfaction, and
notes. Existing catch logging remains separate: a completion record never
creates invented catch entries.

The latest outcome is updated in place for a report so corrections do not
create duplicate completed trips. The report and trip relationship remains
SQLite-authoritative. V7.5.1 can use these records to track recommendation
adherence and feedback without inferring it from catches alone.
