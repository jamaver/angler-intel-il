# V7.5.1.3 Google Drive Export Foundation

Google Drive is optional and disabled by default. It is a secondary copy of
verified runtime backups and generated saved-report JSON/HTML artifacts; it
never becomes an authority or rolls back a successful local SQLite operation.

Configure rclone outside the repository, then set `AI_GDRIVE_ENABLED=1`,
`AI_GDRIVE_REMOTE=anglerdrive`, and optionally `AI_GDRIVE_ROOT=Angler Intel`.
Use `tools/v7_google_drive_upload.py --status --json` to inspect the queue.
The integration uses `rclone copyto`, never `sync`, and does not store OAuth
credentials, tokens, or rclone configuration in the repository or SQLite.
