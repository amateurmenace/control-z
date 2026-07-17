"""Index — the footage librarian. It knows where everything is.

Point it at the folders where footage lives; it catalogs every clip
(duration, size, codec, and the transcript when a Scribe sidecar sits next
to the file) into a local SQLite database, searchable in plain words with
time-coded hits. Selects leave as an FCPXML stringout Resolve imports as a
timeline, or as CSV for the spreadsheet people.

Honest limitations: search is words, not meaning — it finds "crosswalk"
because someone said or typed it, not because a model watched the footage.
Transcripts come from Scribe; run it on what matters. Scanning is on-demand
(the Rescan button), not a background daemon.
"""
