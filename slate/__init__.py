"""Slate — the station graphics kit. It makes it official.

The heart is the lower-third maker: type two lines, pick a style, watch the
real render preview, and export exactly what the timeline needs — ProRes
4444 with real alpha for the edit, PNG stills for the graphics bin, animated
GIF for the web. Around it, the kit covers the rest of what every station
hand-rolls: program slates, SMPTE bars with tone, and countdown leaders.

Rendered locally with Pillow at 2× and downsampled — type stays crisp.
Honest limitations: GIF is 256 colors with 1-bit alpha (web use, not air);
the fancy in/out moves are slide/rise/fade, not a motion-graphics rig —
export the ProRes and keyframe on top when you need more.
"""
