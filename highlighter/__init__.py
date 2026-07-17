"""Highlighter — community meetings, cut down to the moments that matter.

The community-highlighter app reborn on czcore: fetch the meeting (yt-dlp
nightly, checked on every open), read it as text (YouTube captions seed the
transcript instantly; Scribe upgrades it locally), let the scoring pass mark
the moments — every pick names its reasons — and cut the reel from the words.
Local-only processing; the only network is the fetch you asked for.
"""
