# V7.2.4 Catch Reads

The complete JSON catch log is retained as a SQLite comparison envelope while
the application continues returning JSON catches to catch learning and the
catch API. `AI_CATCHES_READ_SOURCE` supports guarded staged modes; a real
SQLite or fallback read also requires `AI_ENABLE_V7_STAGED_READS=1`.

SQLite authority remains disabled.
