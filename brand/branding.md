# Brand + Design Conventions — Community AI Project

<!-- Install at .claude/rules/branding.md — auto-loaded, no import needed.
     To load only on UI work, uncomment the frontmatter block below and move it to the top of the file.
     Maintainer: Stephen Walter. Last updated: July 2026. -->

<!--
---
paths:
  - "**/*.{css,scss,tsx,jsx,html,svg}"
  - "src/components/**/*"
---
-->

## Brand architecture

Four brands. One umbrella, two product studios, one sub-brand.

| Brand | Role | Audience | Volume |
|---|---|---|---|
| **communityai.studio** | Umbrella / manifesto / marketing. The program's argument about AI + civic life. | Funders, press, peer orgs | Medium |
| **publicrecord.studio** | Web app. Track what local government said, across years of meetings. | Residents, journalists, officials | Quietest |
| **civicmedia.studio** | Desktop suite. Video + audio processing tools. | Media makers, PEG stations | Loudest |
| **Control-Z** (`control-z.org`) | **Sub-brand of civicmedia.studio** with its own resource site. Free/open-source finishing tools for the *free* edition of DaVinci Resolve — noise reduction, voice isolation, rotoscoping. Ships Hush (denoise) + Speak (film emulation). | Filmmakers, journalists, community media | Loudest |

**The governing rule: the program is about AI; the products are not.**
`communityai.studio` names AI because the manifesto's argument is about seizing it. At the point of use, AI in a product name invites the hype/skepticism conversation instead of the task. Residents meet *The Public Record*. Operators meet *Civic Media Studio*. Neither needs to know what's under the hood.

**Structural metaphor:** civicmedia is the *press*; publicrecord is the *newspaper*. Tools vs. artifact. This is an **audience split, not a platform split** — never re-brand something merely because it's desktop vs. web.

**Control-Z's dual nature:** it lives inside the civicmedia toolsuite *and* stands alone at `control-z.org` as a public resource hub. In civicmedia contexts, present it as a component. On its own site, it carries full brand identity. It has its own audience (Resolve users) who may never touch anything else in the stack.

Cross-linking: each product footer credits "a Community AI Project tool" → communityai.studio.

---

## Design tokens

Authoritative. Copy verbatim; do not invent values.

```css
:root{
  /* base palette */
  --green-emerald:#059669; --green-deep:#052e16; --green-bright:#22c55e; --green-soft:#4ade80;
  --pop-fuchsia:#d946ef; --pop-purple:#a855f7;
  --ink:#0f172a; --slate:#475569; --slate-soft:#94a3b8; --offwhite:#f8fafc; --white:#ffffff;

  /* semantic */
  --surface-page:var(--offwhite); --surface-card:var(--white);
  --surface-inverse:var(--ink); --surface-brand:var(--green-emerald);
  --text-primary:var(--ink); --text-secondary:var(--slate); --text-muted:var(--slate-soft);
  --text-inverse:var(--offwhite); --text-brand:var(--green-emerald);
  --border-hairline:#e2e8f0; --border-strong:var(--slate-soft); --border-inverse:var(--slate);
  --focus-ring:var(--green-emerald);

  /* per-brand accents (volume: quiet -> loud) */
  --accent-publicrecord:var(--green-deep);
  --accent-communityai:var(--green-emerald); --accent-communityai-pop:var(--pop-fuchsia);
  --accent-civicmedia:var(--pop-purple); --accent-civicmedia-live:var(--green-bright);

  /* type */
  --font-mono:'JetBrains Mono',ui-monospace,monospace;  /* logo lockups (lowercase), headings, labels, code */
  --font-sans:'Inter',system-ui,sans-serif;             /* supporting/body text only */
  --text-xs:11px; --text-sm:13px; --text-base:14px; --text-md:16px;
  --text-lg:20px; --text-xl:24px; --text-display:32px;
  --weight-regular:400; --weight-medium:500; --weight-bold:700; --weight-black:800;
  --leading-tight:1.2; --leading-body:1.55; --tracking-label:0.06em;

  /* spacing + shape */
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px;
  --space-5:24px; --space-6:32px; --space-7:48px; --space-8:64px;
  --radius-none:0; --radius-sm:4px; --radius-keycap:23%;  /* 22/96 of mark box */
  --border-w:1px; --border-w-strong:2px;
  --shadow-none:none;  /* flat vector aesthetic — no drop shadows */
  --dot-grid:radial-gradient(#cbd5e1 1px,transparent 1px);
  --dot-gap:18px 18px;
}
```

**Aesthetic:** "IDE meets civic infrastructure." Terminal glyphs, editor-window chrome (three dots), monospace labels, dot-grid blueprint texture. Flat vector — no gradients heavier than a subtle two-stop, no 3D, no drop shadows. Legacy token prefix on the live site is `--ide-`.

---

## Logo system

Glyph keycaps in a shared 96×96 box, `rx=22`. Same geometry, different glyph and volume. Full asset set (mark / lockup / dark / mono-ink / mono-reversed) is in the Claude Design handoff under `assets/logos/`.

```html
<!-- communityai — terminal prompt: emerald keycap, white chevron, fuchsia cursor -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <rect width="96" height="96" rx="22" fill="#059669"/>
  <path d="M28 33 L49 48 L28 63" fill="none" stroke="#f8fafc" stroke-width="9"/>
  <rect x="52" y="64" width="24" height="7" fill="#d946ef"/>
</svg>

<!-- publicrecord — the minutes: white keycap, slate hairline, three deep-green lines -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <rect x="2" y="2" width="92" height="92" rx="20" fill="#ffffff" stroke="#94a3b8" stroke-width="2"/>
  <rect x="22" y="28" width="52" height="8" fill="#052e16"/>
  <rect x="22" y="44" width="52" height="8" fill="#052e16"/>
  <rect x="22" y="60" width="34" height="8" fill="#052e16"/>
</svg>

<!-- civicmedia — clips under the playhead: ink keycap, green clips, purple playhead -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <rect width="96" height="96" rx="22" fill="#0f172a"/>
  <rect x="18" y="40" width="46" height="11" fill="#22c55e"/>
  <rect x="18" y="58" width="30" height="11" fill="#4ade80"/>
  <rect x="54" y="24" width="6" height="56" fill="#a855f7"/>
  <rect x="46" y="16" width="22" height="12" fill="#a855f7"/>
</svg>
```

**Rules**
- Lockups are **lowercase JetBrains Mono** + full domain (`communityai.studio`), mark on the left.
- Must survive at **18px** and as a favicon. No detail that dies at that size.
- Light-bg, dark-bg, and one-color variants exist — use them; never recolor marks ad hoc.
- **publicrecord takes zero fuchsia.** Ever. Neutrals + deep green only.
- Control-Z has no keycap mark yet. **TODO:** needs one in the same system — undo-arrow glyph, civicmedia's ink + purple palette.

---

## Volume rules

Same voice, different amplitude. Enforce per property.

- **publicrecord — quietest.** Neutrals + deep green. Institutional, calm, ledger-like. No jokes, no terminal cosplay in primary UI. Test: *would a skeptical 70-year-old town-meeting regular trust this?*
- **communityai — medium.** Emerald primary + exactly one fuchsia pop per view. Activist-optimistic, manifesto energy.
- **civicmedia / Control-Z — loudest.** Ink surfaces + purple + bright green. Full IDE/broadcast energy. Operators like the console look.

---

## Naming + copy conventions

- Tools are prefixed **`Community <Noun>`** (Captioner, Highlighter, Translator, Narrator, Publisher) or **`Civic <Noun>`** (Civic Documenter). ⚠️ *Unresolved: the site says "Civic Translator," recent docs say "Community Translator." Normalize.*
- Standalone brands break the prefix: **Control-Z**, **Driftwood**, **Command-Z**, **Artificial**, **Commit**, **Anti-AI**.
- Domains and lockups are always lowercase.
- Voice = "Ballistic Neue": essayistic, em-dash-heavy, parenthetical, high theory next to dry humor.
- Product copy is **benefit-forward** — sell the payoff, not the mechanism ("find the 40 seconds that matter in a four-hour meeting," not "diarized transcript search").
- Content license `CC BY-SA 4.0`; code is **AGPL-3.0** (closes the SaaS loophole so vendors can't fork civic code into a hosted black box).
- Standard credit string:
  `designed + developed by Stephen Walter with Brookline Interactive Group & Neighborhood AI · CC BY-SA 4.0`

---

## Live URLs

Captioner `caption.weirdmachine.org` · Highlighter `community-highlighter.onrender.com` · Artificial `artificial.weirdmachine.org` · Translator `translator.weirdmachine.org` · Commit `commit-ai-civic-agent-390658405112.us-west1.run.app` · Civic Documenter `documenter.weirdmachine.org` · Control-Z `control-z.org` · Driftwood `cmd-z.com/home` · Neighborhood AI `neighborhood-ai.netlify.app` · Command-Z `command-z.org` · Hush/Speak `amateurmenace.github.io/Hush-OpenNR/` · Anti-AI `anti-ai-89463051012.us-west1.run.app`

**Specced, not built:** Community Memory, Community Narrator, Community Publisher, Community AI in a Box.

`projects.js` on community.weirdmachine.org is the **source of truth** for descriptions/URLs. Update there first.

---

## Open questions

1. **Command-Z vs Control-Z.** `command-z.org` describes an "undo button" family of civic + creative tools — which reads as a parent to Control-Z and Driftwood. Control-Z is now fixed as a civicmedia sub-brand, so Command-Z's position is undefined. Resolve before it calcifies.
2. `Civic Translator` vs `Community Translator` — normalize the prefix set.
3. Neighborhood AI resolves to a Netlify app in `projects.js` but `neighborhoodai.org` in partner credits. Pick canonical.
4. Control-Z needs a keycap mark in the logo system.
