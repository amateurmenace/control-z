# brand/ — the civic-tech logo system

Canonical brand assets for the four-brand family. **Source of truth for the
rules is [`branding.md`](branding.md)** in this folder (tracked) — colours, type,
volume, naming, do/don't. A mirror is installed at `.claude/rules/branding.md` so it
auto-loads each session (that path is gitignored; the copy here is canonical). This
directory also holds the assets the doc refers to. Do not invent token values or
recolour marks by hand; place these SVGs.

## Brand architecture

| Brand | Domain | This repo | Volume |
|---|---|---|---|
| **communityai.studio** | umbrella / manifesto | (external) | medium |
| **publicrecord.studio** | The Public Record web app | `web/` → `site/docs/app/` | quietest |
| **civicmedia.studio** | Civic Media Studio desktop suite | `suite/` + `packaging/` | loudest |
| **Control-Z** | `control-z.org` resource site — **sub-brand of civicmedia** | `site/` → `site/docs/` | loudest |

## logos/ — 18 SVGs, 3 brands × 6 variants

Direction: **glyph keycaps** — one 96×96 rounded-square keycap (`rx=22`), only
the glyph + ink change per brand.

- `{brand}-mark.svg` — the keycap (light bg). Favicon-safe to 16px.
- `{brand}-mark-dark.svg` — for ink/dark backgrounds.
- `{brand}-mark-mono-ink.svg` / `-mono-reversed.svg` — one-colour (outline) variants.
- `{brand}-lockup.svg` / `-lockup-dark.svg` — mark + lowercase mono wordmark.

Glyphs: **communityai** = emerald keycap, white chevron `>`, fuchsia cursor ·
**publicrecord** = off-white keycap, deep-green "minutes" lines, **zero fuchsia** ·
**civicmedia** = ink keycap, green clips under a purple playhead.

> ⚠ **Control-Z has no keycap mark yet** — a documented TODO in `branding.md`
> (undo-arrow glyph, civicmedia's ink+purple). Don't fabricate one.

## tokens/ — colors.css · typography.css · spacing.css

The CSS-variable source. Emerald `#059669` primary; JetBrains Mono for
lockups/headings/labels/data/code, Inter for body only. Flat vector, no drop
shadows, hairline borders. Per-surface volume: publicrecord = neutrals + deep
green only; communityai = emerald + one fuchsia pop; civicmedia/Control-Z =
ink + purple + bright green.
