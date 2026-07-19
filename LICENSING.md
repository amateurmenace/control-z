# Licensing

This project is splitting into two repositories, and they will not carry the
same licence. That is deliberate, and the reason is narrow enough to state in
one sentence: one of these things is a hosted service and the other is a
desktop tool, and copyleft only has teeth against the first.

What follows is the whole argument, in plain English, for the people who have
to make a decision about it — a funder deciding whether the money buys
something durable, a peer station deciding whether to run it, a journalist
deciding whether to trust it, a town counsel deciding whether the town can
sign.

**This is an explanation, not legal advice.** Nobody here is a lawyer. Where a
question is genuinely a legal question, this document says so and stops.

---

## The two repositories

| Repository | What it holds | Licence |
|---|---|---|
| **control-z** | `czcore` and the nine DaVinci Resolve tools — pivot, stencil, scribe, clear, rise, depth, grabber, slate, indexer | **MIT** |
| **the civic stack** | `brand`, `memory`, `web`, `record`, `highlighter`, `publisher`, `interpreter`, `narrator`, `suite` | **AGPL-3.0** |

The civic stack installs control-z from PyPI the way it installs any other
dependency. Nothing flows the other way: control-z is a clean leaf, proven to
have zero imports into the civic stack, which is what makes the split possible
at all rather than merely desirable.

MIT is compatible with AGPL-3.0 in the direction that matters here. Permissive
code can be pulled into a copyleft work; the reverse is not true. So the civic
stack may bundle, vendor, or depend on the Resolve tools freely, and the
Resolve tools stay unencumbered for everyone else.

## Why the two differ

The AGPL's distinguishing feature is section 13 — the network clause. It says
that if you modify the software and let people use it *over a network*, you
have to offer those users the source of your modified version. This is the
only meaningful difference between the AGPL and the ordinary GPL, and it only
fires when there is a network service in the picture.

`publicrecord.studio` is exactly that. It is a hosted civic record: residents
open a browser, the server answers. Section 13 is live, and it is doing the
work we want done.

A Resolve plugin is the opposite case. It runs on an editor's laptop, on that
editor's own footage, with nothing uploaded and no server anywhere. Section 13
never fires, and an AGPL badge on a desktop finishing tool buys nothing except
a reason for a cautious IT department to say no. For those tools MIT is the
better licence on the merits: it maximises adoption, which for a free
alternative to a paywalled feature is the entire point.

Same programme, same politics, two different physics. The licences follow the
physics.

## What the AGPL actually obliges

Concretely, and without hedging:

**If you fork the civic stack, change it, and run it as the public record for
your town, your residents can ask you for the source of the version you are
running — and you have to give it to them.** Not the source we published. The
source you are actually serving, modifications included, under the same
licence.

That is the obligation. It is not onerous and it is not vague. In practice it
means publishing your fork.

## What the AGPL does not oblige

A great deal less than people expect, and worth naming item by item, because
the fear of copyleft is usually larger than copyleft.

- **Reading the record obliges nothing.** A resident who opens a meeting page
  incurs no duty of any kind. The licence binds people who distribute or host
  the software, never people who read what it publishes.
- **Using the software obliges nothing.** Download it, run it, use it for your
  station's own work. No trigger.
- **Running it unmodified is fine.** Section 13 asks for *your modified
  version*. If you deploy what we published, without changes, there is nothing
  additional to offer — the source is already public, and pointing at it
  suffices.
- **Internal use is fine.** Modify it all you like for a service only your own
  staff use. The clause speaks to the users you let interact with it remotely.
  Where "your own staff" shades into "the public" is a judgement call, and if
  your deployment sits near that line, ask a lawyer rather than this file.
- **Your content is not covered.** The AGPL is a software licence. It governs
  the code, not the meetings, the transcripts, the issue pages, or the
  glossaries. Those carry **CC BY-SA 4.0** (see `.claude/rules/branding.md` and
  `NOTICE`). Two licences, two bodies of material, no interaction between them.
- **It does not reach your other software.** Running an AGPL service on the
  same machine as something else does not license the something else. The
  boundary is the program, not the server.

## Why a civic record specifically wants this

The AGPL exists because the GPL had a gap, and the gap had a name: software as
a service. Under the GPL, obligations attach to *distribution* — handing
someone a copy. A company that never hands out copies, and instead runs the
software on its own machines and sells access, distributes nothing, and so owes
nothing. Take free code, improve it in private, rent it back. Entirely legal,
and for two decades entirely routine.

For most software that gap is a nuisance. For a public record it is the whole
threat model.

Consider how the failure actually goes. A town pays for this work, or a grant
does, which is the same public money by a different route. The code is open, so
a vendor takes it — permitted, and fine. The vendor hosts it, adds the
integrations a town procurement office wants, and sells the town a subscription
to its own meetings. The improvements stay private because nothing was ever
distributed. Five years on, the town's record of itself lives inside a product
it does not control, cannot inspect, and cannot leave, and the archive that was
supposed to belong to the public belongs to whoever holds the database.

The AGPL closes that door. A vendor may still host this and still charge for
it — that is allowed, and it is a legitimate way to make civic software
sustainable. What the vendor may not do is keep the improvements. Every fork
running as a public service stays open, so the town can always see what is
running, always take it elsewhere, and always get back the work done on its
behalf.

The record is public. The code that keeps it should be too. Under the AGPL that
stays true no matter who ends up operating it.

## The relicensing, stated honestly

This repository was MIT until now. That has consequences, and pretending
otherwise would be both wrong and pointless.

**A licence already granted cannot be withdrawn.** Every version released under
MIT is MIT permanently, for everyone who has it and everyone who gets it later.
The relicensing is forward-looking only: it applies to new releases of the
civic stack, not to anything already published.

In practice: the tagged releases through **v1.9.0** are MIT and remain MIT
forever. Anyone who wants the MIT terms for the civic stack can take v1.9.0,
fork it, and do as they please, subject only to MIT. Nobody loses a right they
already had. What changes is the terms on which *future* work is offered.

The 2.0.0 line is the split point — the release where `control-z` and the civic
stack stop being one repository. As of this writing 2.0.0 is not tagged; the
last tag is v1.9.0. If 2.0.0 ships as the first AGPL release of the civic
stack, then the MIT boundary is v1.9.0 and the sentence above is exact. If some
part of 2.0.0 ships under MIT first, the boundary moves accordingly, and **this
paragraph must be corrected to name the real last-MIT tag before the split is
announced.** Getting this line wrong is the kind of error that is quoted back
at you.

The Resolve tools are unaffected. They were MIT, they stay MIT, and the
covenant printed in their README — free forever, works with the free version of
Resolve, local-only, shows its work — is unchanged.

### The copyright question, unresolved

**Read this part before relying on any of the above.**

Relicensing is a right of the copyright holder. It follows that the civic stack
can only move to AGPL-3.0 if everyone who holds copyright in it agrees.

The current `LICENSE` file names the copyright holder as **"Weird Machine /
Brookline Interactive Group."** `NOTICE` and the project's standard credit
string name **Brookline Interactive Group** and **Neighborhood AI** as
collaborators. Whether those are attributions of partnership and funding, or
assertions of copyright in contributed code, cannot be determined from the
repository. The git history shows a single author identity, but git authorship
is evidence about who typed, not about who owns — work for hire, grant terms, a
contributor agreement, or an institutional policy can all place copyright
somewhere other than the commit line.

So this is an open legal question, and it is a blocking one:

> Does anyone besides Stephen Walter hold copyright in the civic stack's code?
> If Brookline Interactive Group or Neighborhood AI hold any, their written
> agreement is required before the relicensing is valid.

`specs/12-community-program.md` §9 already lists AGPL ratification as an open
question blocking In-a-Box Phase 1, which suggests this was known and has not
been closed. It should be closed in writing — a short signed acknowledgement
from each named party is enough — before the split is executed, and certainly
before the AGPL is described publicly as settled.

## Third-party code, and why the AGPL sits comfortably with it

The stack ships and downloads a lot of other people's work. None of it
conflicts with AGPL-3.0, and the reasons differ by category. `NOTICE` carries
the full inventory; this is the reasoning behind it.

**The permissive licences — MIT, Apache-2.0, BSD-3-Clause.** These are the ML
models, ONNX Runtime, OpenCV, CTranslate2, sherpa-onnx. Permissive licences
impose conditions on attribution and little else, and none of them forbids
distribution under stronger terms. They flow into a copyleft work in one
direction, which is the direction we need. Their notices must travel with the
software, which is what `NOTICE` is for.

Apache-2.0 deserves a specific note, because it is the one real trap and the
AGPL avoids it. Apache-2.0's patent-termination provision is incompatible with
**GPLv2**, and always has been. It is compatible with the **version 3** family,
which was drafted with exactly that in mind. AGPL-3.0 is in the version 3
family. So the Apache-licensed components — YOLOX, SAM 2.1, 3D-Speaker,
OpenCV, sherpa-onnx — are fine here, and would not have been under an older
copyleft licence.

**The models are mostly not a combination question at all.** They are
downloaded on first use, not bundled — third-party works fetched at runtime,
each with its own licence card shown before download and its own pinned
SHA-256. The licence of a file the user obtains from its own publisher is
governed by that publisher, not by ours.

**FFmpeg, LGPL-2.1-or-later.** The packaged app bundles a shared-library FFmpeg
built without `--enable-gpl`, `--enable-version3`, and `--enable-nonfree`.
"or-later" is the operative phrase: it permits use under LGPL-3.0, and LGPL-3.0
is GPL-3.0 with additional permissions attached. The version 3 copyleft family
is designed to combine with itself, and the AGPL and GPL are explicitly made to
work together — AGPL-3.0 §13 provides for exactly that combination. So the
combination is sound.

The LGPL's own obligation is separate and survives all of this: users must be
able to replace the FFmpeg libraries with their own build. `NOTICE` states how
— the pinned upstream tarball and the complete build configuration are in
`packaging/build_ffmpeg.sh`, and because the signed bundle's hardened runtime
refuses a substituted library, the relink freedom is exercised by rebuilding
from source. That obligation is owed to the LGPL and is not altered by which
licence the surrounding application carries. The same applies to libsndfile,
which ships its COPYING beside it.

**The content is separate.** `interpreter/glossaries/*.json` and the record's
published material are CC BY-SA 4.0. Creative Commons licences are not software
licences and are not being combined with one; they sit alongside. Nothing about
the AGPL reaches them, and nothing about CC BY-SA reaches the code.

One honest caveat on this whole section: licence compatibility is reasoning
about legal documents, and reasoning can be wrong. The analysis above is stated
so it can be checked, not so it can be taken on faith. If a deployment or a
procurement turns on it, have a lawyer read it.

## Where the files are

- `LICENSE` — MIT, the Resolve tools.
- `LICENSE-AGPL-3.0.txt` — the complete GNU Affero General Public License,
  version 3, verbatim from the Free Software Foundation.
- `NOTICE` — third-party inventory: bundled libraries, downloaded models,
  shipped data, and which licence covers which.
- `.claude/rules/branding.md` — the CC BY-SA 4.0 content position and the
  standard credit string.
- `specs/17-studio.md` §9 — where AGPL on `record/` was first asserted.
- `specs/12-community-program.md` §9 — where ratification is listed as open.

---

designed + developed by Stephen Walter with Brookline Interactive Group &
Neighborhood AI · CC BY-SA 4.0
