# control-z.org — suite site, implementation spec

Retrofit control-z.org from "the Hush page (with a Speak tease)" into the home of the
suite. Keep what's working: the warm **cream/paper** look (not another black plugin
site), Space Grotesk display + SF Mono details, the interactive node-tree, the
reproducible bake-to-static build. Scale all of it from 2 tools to 8+.

## 1. Repo & build

- Lives at `control-z/site/` in the monorepo now; graduates to its own repo (`control-z-site`)
  at launch, taking the `CNAME` with it. DNS untouched (domain already points at Pages).
- **Builder:** Python + Jinja2 (`site/build.py`) — the natural upgrade of the existing
  token-replacement `build_site.py`. No JS build chain, no framework. Output = fully
  static, view-source-friendly pages in `docs/` (Pages root).
- Content is **data-driven**: one `content/tools.yaml` feeds the homepage map, tool pages,
  roadmap, and the GitHub org README table later. Adding a tool = one YAML block + one
  template include.
- Keep the **Squarespace embed** path: `build_embed.py` generalizes to emit a scoped
  fragment per tool for BIG's site.
- Images: small UI shots inlined base64 (current pattern); video/heavy media from Pages
  asset URLs (never cross-repo Pages links — the Hush-OpenNR rename taught that).

```
site/
  build.py                 # jinja2 render + asset baking + RSS
  content/
    tools.yaml             # the single source of truth (schema below)
    news/*.md              # posts (front-matter: date, title, tool?)
    copy/*.md              # mission, stations, toolbox prose
  templates/  base / home / tool / roadmap / stations / mission / toolbox / news
  static/     tokens.css · site.js · map.js · img/
docs/                      # baked output + CNAME  (Pages root)
```

### tools.yaml schema

```yaml
- id: pivot
  name: Pivot
  verbline: "Pivot follows the subject."
  status: shipped | beta | in-progress | proposed     # gates where it may appear
  accent: "#5B7A9E"
  stage: deliver | restore | edit | sound | color     # pipeline-map column
  audiences: [stations, journalists, filmmakers, artists]
  replaces: [{name: "Studio Smart Reframe", price: "$295 (Studio)"},
             {name: "Opus-style SaaS", price: "$15+/mo"}]
  platforms: [macos, windows, cli]
  repo: https://github.com/…      releases: …/releases/latest
  page: {demo: pivot-demo.mp4, before: …, after: …}
```

## 2. Design tokens (extend the existing `:root`, don't replace it)

Existing, kept: `--cream #F5F3EE · --card #FFF · --green #3D5A47` (Hush) `· --orange
#E89D6B` (Speak) `· --amber #E5A835 · --dark #2D3A2E` + radii/mono stack.
New per-tool accents (muted to sit on cream at the green/orange saturation level):

| Tool | Accent | | Tool | Accent |
|---|---|---|---|---|
| Pivot | slate `#5B7A9E` | | Clear | teal `#4A8C7E` |
| Stencil | plum `#8E6A9E` | | Rise | gold `#C99A3A` |
| Scribe | ink `#52678C` | | Depth | indigo `#5E5A8C` |

Rule: accents color *identity moments* (node glow, h3, badges, links on that tool's page);
body stays green-on-cream everywhere so the suite reads as one publication.

## 3. Information architecture

```
/            the suite: hero + covenant strip + PIPELINE MAP + latest news
/hush /speak /pivot /stencil /scribe /clear /rise /depth     (tool template)
/roadmap     proposed catalog + voting via GitHub Discussions links
/stations    PEG deployment guide, submission-QC story, training, ACM pitch
/mission     covenant, Community AI, the coalition (Weird Machine × BIG)
/toolbox     curated free tools we recommend instead of rebuilding
/news        posts + RSS
```

Homepage shows **shipped / beta / in-progress only**. `proposed` renders exclusively on
/roadmap. No vaporware on the front page — covenant applied to marketing.

## 4. The homepage pipeline map (the centerpiece)

The existing Hush↔Speak node-tree sim (`site/index.template.html` ~line 286+) scales into
a suite map — reuse its node card CSS/JS wholesale:

- Horizontal flow: **RESTORE → EDIT → SOUND → COLOR → DELIVER** (stages from tools.yaml),
  rendered as node cards on a connecting spine, exactly like the current `.nt` nodes.
- Node states: **lit** (shipped — accent border + glow, like `.nt.hush.sel` today),
  **breathing** (beta/in-progress — subtle pulse + "in progress" tag), absent (proposed).
- Click a node → its tooltip card (the current `data-t/data-b` pattern) with verbline +
  one-liner + CTA to the tool page.
- **Audience chips** above the map — Stations · Journalists · Filmmakers · Artists —
  filter-relight nodes via `data-audience`. URL-hash addressable (`/#stations` deep link
  for the BIG newsletter).
- Mobile: map collapses to a vertical stage list (CSS only). `prefers-reduced-motion`:
  no pulse/glow animation. Full keyboard nav (nodes are `<a>`s, chips are buttons).
- Hero above it: **"Undo the paywall."** + subline + the covenant strip (5 badges:
  Free forever · Open source · Works in free Resolve · Local only · Shows its work).
- Below: the "money undone" counter (release-download counts × replaced-tool prices,
  fetched at *build time* from the GitHub API, labeled "our estimate").

## 5. Tool page template (sections, in order)

1. Hero: name + verbline, accent-tinted; 30-sec demo or before/after slider (reuse
   Hush's slider component).
2. **Replaces strip:** cards from `replaces:` — respectful tone, Hush's "coming from
   Studio's NR palette?" table is the model.
3. Covenant badges + platform/OS badges + download buttons (GitHub releases API at build
   time for version/size).
4. Quick start (numbered, 4 steps max) → Controls/docs → Recipes (Resolve roundtrip
   screenshots — for Stencil/Depth/Scribe this section *is* the product).
5. **Model card** (AI tools): model, license, source, what it was trained to do, what we
   rejected and why (e.g. "larger Depth-Anything checkpoints are non-commercial — we
   don't ship them").
6. **Honest limitations** (required, hand-written per tool).
7. White paper link (when it exists) · Changelog · GitHub link.

Hush and Speak port into this template first — they validate it before any new tool ships.

## 6. Copy draft (hero + verblines, editable)

> **Undo the paywall.**
> control-z is a suite of free, open-source finishing tools for DaVinci Resolve — built
> with community media centers, journalists, filmmakers, and artists in mind. Professional
> results, no license key, and your footage never leaves your machine.

Verblines: *Hush quiets the noise. Speak gives the image its voice. Pivot follows the
subject. Stencil traces the subject. Scribe writes it all down. Clear rescues the voice.
Rise restores the detail. Depth measures the scene.* (Stencil/Pivot both "subject" —
alt for Stencil: "Stencil cuts the subject out." Pick at copy pass.)

Footer, every page: "control-z is part of the **Community AI Project** — AI that runs
locally, serves communities, and stays free." → community.weirdmachine.org.

## 7. Migration & launch checklist

- [ ] Build new site in `control-z/site/`, bake to its `docs/`
- [ ] Port Hush content into tool template (keep every anchor that exists today:
      `/#download`-style links from old posts get JS anchor redirects)
- [ ] Speak page honest status: in-progress until it ships — breathing node, no download
- [ ] Graduate `site/` → `control-z-site` repo; enable Pages; move `CNAME` there;
      re-verify custom domain; confirm HTTPS
- [ ] Replace `Hush-OpenNR/docs/` content with meta-refresh redirects → control-z.org/hush
      (repo keeps hosting release binaries only)
- [ ] Update Hush README header links + GitHub repo description + release-notes footer
- [ ] Verify every price/feature-gate claim (Studio gating changes per Resolve release)
- [ ] Launch post: "Hush grew a family" (news + RSS, r/davinciresolve, BIG newsletter,
      Community AI channels); Squarespace embed refresh for BIG
- [ ] Lighthouse pass ≥95 across the board; axe a11y clean; test at 360px width

## 8. Acceptance

A stranger landing on control-z.org understands in 10 seconds: *free pro tools for the
free version of Resolve, made for people like me* — and can reach a working download in
two clicks. A returning Hush user's old links still resolve. Adding tool #9 touches
`tools.yaml`, one news post, and nothing else.
