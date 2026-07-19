# 18 — The split: two repositories, two licences, one seam

The monorepo has been right for eighteen months and is now wrong for two
reasons at once. The first is legal: AGPL-3.0's network clause only bites a
hosted service, and exactly one thing here is hosted. The second is
audience: a filmmaker who wants Pivot and Scribe should not have to clone a
Postgres corpus, a steward console and four brands to get them.

So the tools leave, and they leave under MIT.

This spec is the runbook. It is written to be executed once, by a human, on
a day with nothing else in it. It is honest about what the split costs,
because the cost is not small and it is mostly paid *after* the split, not
during it.

**Nothing here has been executed.** Every command below is a draft.

---

## 1. The two repositories

### Repo 1 — `control-z` (MIT)

The nine Resolve tools and the core they share.

```
czcore/    pivot/   stencil/  scribe/  clear/
rise/      depth/   grabber/  slate/   indexer/
grades/    packs/
```

`grades/` and `packs/` travel with it: they are the Resolve-side artifacts
(the middle-gray anchor, the node tree, the Fusion template zip), and
`packs/build_zip.py` imports `depth.cli` to rebuild the pack from
`depth/templates/`. They belong to the tools, not to the desk.

**Licence: MIT, unchanged.** For a desktop plugin the network clause is
inert; MIT is what maximises adoption, and adoption is the whole argument
for a free finishing suite aimed at the *free* edition of Resolve.

**Audience:** filmmakers, journalists, community media, anyone who opens
Resolve. They arrive through control-z.org and may never learn that a civic
stack exists.

**Verified clean.** No file under those ten packages imports anything from
the civic side. Checked directly, not assumed:

```
grep -rnE '(from|import) (brand|memory|web|record|highlighter|publisher|interpreter|narrator|suite)\b' \
  czcore pivot stencil scribe clear rise depth grabber slate indexer --include='*.py'
```

returns nothing. This is a leaf, and it is the only reason the split is
cheap in one direction.

### Repo 2 — the civic stack (AGPL-3.0)

```
brand/    memory/   web/     record/   highlighter/
publisher/  interpreter/  narrator/  suite/
site/     packaging/    docker-compose.yml
```

**Licence: AGPL-3.0.** The clause that matters is §13: run a modified
version as a network service and you owe your users the source. That is
precisely the failure mode the civic record must foreclose — a vendor
forking a town's public record into a hosted black box.

**Audience:** two, and they are different people. `web/` and `record/`
serve residents and journalists under publicrecord.studio. `suite/` and the
community wing serve station operators under civicmedia.studio. Both live
here because both are downstream of `memory/`.

**It depends on repo 1.** Ten packages import across the seam, and rather
more than the shorthand suggests:

| package | imports from repo 1 |
|---|---|
| `suite/` | czcore, clear, depth, grabber, indexer, pivot, rise, scribe, slate, stencil |
| `memory/` | czcore, grabber, indexer, scribe |
| `highlighter/` | czcore, slate |
| `publisher/` | czcore, slate |
| `interpreter/` | czcore, scribe |
| `narrator/` | czcore |
| `record/` | czcore |
| `web/` | czcore |
| `brand/` | nothing |

`suite/` importing all ten is the honest number. Most of those are
function-level imports inside `suite/tools/*.py`, deferred so the desk
starts fast — deferred is not optional, it is only late. Every one of them
must resolve at runtime in a frozen app.

`brand/` imports nothing and is imported by nothing: it is a data package
of eighteen SVGs and three token sheets. Note that `web/emit.py` inlines
the publicrecord mark by hand rather than reading `brand/logos/` — a
divergence risk that predates this split and is not fixed by it.

---

## 2. History

### The asymmetry that decides this

155 commits. 12 merges. Of the 143 non-merge commits:

- **56** touch only civic-side paths
- **11** touch only tool-side paths
- **31** touch both
- **45** touch neither — specs, tests, packaging, README, CHANGELOG, root

Read that again. Repo 2 is not a piece of this history; repo 2 is
substantially *all* of it. 101 of 143 commits are either civic-only or
repo-wide. The tools account for eleven commits of their own and share
thirty-one.

That asymmetry is the whole answer.

### The options, weighed

**`git filter-repo --path`.** Rewrites history keeping only named paths,
pruning commits that become empty. It handles the twelve merges correctly —
a lane merge that touched no tool path becomes degenerate and is pruned,
which is right, though it means the extracted history will not resemble
main's shape. Its real cost is the 31 both-side commits: each appears in
*both* repositories carrying half its diff and all of its message. "The
three lanes land, and a clean merge that wasn't" will sit in repo 1
describing work that is not there. No tool avoids this. It is intrinsic to
cutting a commit in half.

Its other cost is that every SHA changes. CHANGELOG entries, release notes
and project-memory files that cite SHAs (`tag at 5d1c681`) become dead
references in whichever repo was rewritten.

**`git subtree split -P <dir>`.** Splits *one* directory into its own
branch. Repo 1 is ten directories. There is no coherent way to fuse ten
subtree histories into one repository without a synthetic octopus merge
that no one will ever read. Wrong tool. Rejected.

**Clean start plus preserved archive.** Repo 1 begins at a single commit —
"the tools, extracted from the monorepo at `<sha>`" — and the monorepo is
kept frozen as the archive of record. `git blame` on repo 1 goes blind, but
only one checkout away. Costs an afternoon instead of a day, and is
perfectly reversible because nothing was rewritten.

### The recommendation

**Do not rewrite the monorepo. Repo 2 *is* the monorepo.**

Delete the ten tool directories in one commit, relicense, rename on GitHub.
Every SHA survives. Every tag still points at a real object. gh-pages,
releases, release assets, and the seven deploy commits that put the record
on control-z.org all keep working. This costs one commit and buys the
entire history of the side that has most of it.

**Extract repo 1 with `git filter-repo`, from a fresh clone.**

Eleven tool-only commits plus a share of thirty-one is worth keeping, and
filter-repo is the only tool that keeps it. Accept the half-diff commits;
accept the SHA churn (repo 1's SHAs are cited nowhere that survives
anyway); **drop the inherited tags**, because `v1.0.0` through `v1.9.0`
were suite releases and mean nothing in a repository with no suite.

**Keep the monorepo mirror regardless.** Even with repo 2 unrewritten, the
frozen mirror is what makes step 4 reversible and what holds the tools'
blame in its original shape. It costs 78 MB.

The commands are in §5.

---

## 3. The dependency contract

This is the hardest question in the split and the one most likely to be got
wrong quietly.

### What the answer must satisfy

Four constraints, and they do not all pull the same way.

1. **`packaging/suite.spec` must freeze repo 1's code into the DMG.**
   PyInstaller walks imports in a venv. It does not care where the code came
   from — only that it is importable and that its package data is reachable.
2. **The desk is distributed as a signed app, not a pip install.** The user
   never runs pip. Whatever the contract is, it is resolved once at build
   time on Stephen's Mac, and the result is sealed under the hardened
   runtime.
3. **The record is a container.** `record/` installs by pip into an image.
   That path genuinely needs a resolvable dependency, not a checkout.
4. **Development continues across the seam.** 31 of 143 commits touched
   both sides. That rate will fall after the split but it will not fall to
   zero.

### The options

**A PyPI package.** `pip install control-z`, and repo 2 pins
`control-z==2.0.0`. The cleanest thing to depend on: resolvable from an
index, reproducible, and the only option under which a stranger can install
repo 1 alone — which is the adoption argument that justified MIT in the
first place. Two costs. First, it starts a release train: every repo-1
change repo 2 needs must be published before repo 2 can use it, and a PyPI
version can be yanked but never deleted. Second, repo 1's pyproject
currently declares `dependencies = []` and leans on `requirements.txt`.
Uploading that produces a package that installs cleanly and then dies on
`import numpy`. Publishing forces repo 1 to finally declare real
dependencies — good hygiene, but work.

**A git URL pin.** `control-z @ git+https://github.com/…@<tag>`. No index,
no release train, exact reproducibility from a tag, and pip installs it as
a real distribution — which is all PyInstaller needs. The cost is stated
already in this repo's own pyproject, in the `sam-2` comment: a direct
reference bars the depending project from an index upload. Repo 2 can never
go on PyPI while it pins a git URL. That is fine — repo 2 ships as a signed
app and a container, neither of which is `pip install`ed by strangers.

**A vendored subtree.** One checkout, hermetic build, no install step. It
also puts two copies of the tools in the world and invites the desk lane to
edit the vendored one. That is the failure the split exists to prevent, and
PARALLEL.md exists because it already happened once inside a single repo.
Rejected outright.

### The decision

**Phase 1, from day one: a git URL pinned to a tag.**

```toml
# repo 2 pyproject.toml
dependencies = [
  "control-z @ git+https://github.com/amateurmenace/control-z-tools@v2.0.0",
]
```

A tag, never a branch. A branch pin means the DMG built on Tuesday and the
DMG built on Wednesday are different apps with the same version number, and
nothing in the artifact records which.

**Phase 2, once repo 1's surface stops moving weekly: publish to PyPI** and
the pin becomes `control-z>=2.0,<3`. Do not do this on day one. A release
train is a promise, and promising one while the seam is still settling is
how you end up publishing 2.0.7 because a keyword argument moved.

**The development escape hatch, and its gate.** Day to day, the two repos
sit as siblings and repo 2's venv carries `pip install -e ../control-z`.
That is correct for development and catastrophic for a release. This repo
has been bitten twice by exactly this shape: v1.1 shipped against a stale
editable install, and 1.9.0 nearly shipped a Suite whose pypdf existed only
as a hiddenimport — a hiddenimport is not an installation, and an editable
install is not a dependency.

So gate it. `packaging/build_suite.sh` must refuse to build when the
installed `control-z` distribution is editable:

```sh
python - <<'PY' || exit 1
import sys, json
from importlib.metadata import distribution
d = distribution("control-z")
try:
    url = json.loads(d.read_text("direct_url.json") or "{}")
except Exception:
    url = {}
if url.get("dir_info", {}).get("editable"):
    sys.stderr.write(
        "control-z is installed editable. A signed build must freeze a "
        "pinned distribution, not a checkout.\n")
    sys.exit(1)
PY
```

and `tests/test_packaging.py` gets the same assertion, so the refusal is a
test failure on the dev Mac rather than a discovery at notarization.

### The spec edits this forces

`packaging/suite.spec` reaches into repo-1 paths that will no longer exist
beside it:

```python
(str(REPO / "depth" / "templates"), "depth/templates"),
```

`REPO` is `SPECPATH.parent` — repo 2's root. After the split there is no
`depth/` there. That line must resolve through the installed package:

```python
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files("depth", includes=["templates/*.setting"])
```

with the destination verified to land at `depth/templates`, because
`depth/engine.py` resolves `parents[2]/templates` with no `_MEIPASS` branch
and will not tell you it failed — it will render without the pack. The same
check applies to `pivot/static/*.html`. Both are already declared in repo
1's `package-data`; carry that block across verbatim.

`pathex=[str(REPO)]` stops covering repo 1 and starts being redundant. Leave
it; note in the comment why it no longer means what it said.

`hiddenimports` still names `grabber`, `indexer`, `slate` — all repo 1 now,
all still reached only through deferred imports, all still needing to be
named. Nothing changes there except that the comment is now describing a
cross-repo fact.

### The part I cannot answer

Whether shipping a signed AGPL application that bundles MIT code satisfies
§13's corresponding-source obligation by linking two repositories and
pinning a tag in the release notes — that is a lawyer's question and I am
not one. The standard practice is to link both and pin the SHA, and this
runbook assumes it. **specs/12 §9 still lists AGPL ratification as an open
question blocking In-a-Box Phase 1. It is still open. This spec does not
close it.**

**Consent is settled, and it was settled by asking the only person who could
know.** An earlier pass in this session reasoned from `git shortlog` that a
single author meant a single owner, which is not a valid inference — authorship
records who typed, and employment, commission or grant terms can move ownership
elsewhere. A later pass read the `LICENSE` file naming *"Weird Machine /
Brookline Interactive Group"* and treated that as a live claim by a second
party. Both were the same mistake in opposite directions: guessing at a fact
that is not in the repository.

The fact, from the holder: **copyright is Stephen Walter's**, working under the
trade name Weird Machine, which is a brand and not a legal entity. Brookline
Interactive Group and Neighborhood AI are **partners** — credited on every
footer, in `NOTICE`, and in the standard credit string, and named there because
that is where partners belong. The old `LICENSE` line put a partner on the face
of the grant, which overstated their role and left the actual holder unnamed;
it now reads `Copyright (c) 2026 Stephen Walter (Weird Machine)`.

So the relicensing needs no third-party sign-off. What it still deserves is a
note to both partners before the AGPL repository is public — not to obtain
permission, but because a partner should hear the licence of the thing they are
credited on from the project rather than from GitHub.

What *is* certain: **everything already released under MIT stays MIT
forever.** Anyone may fork repo 2 at the last pre-split commit and continue
under those terms. A licence already granted cannot be withdrawn, and the
boundary is a real tag — `v1.9.0`, the last one cut. `v2.0.0` is built,
signed and notarized but **not tagged**, so if it ships before the split it
ships MIT and the boundary moves with it.

---

## 4. What breaks on day one

### The test suite

56 files, and the naming lies. A test goes where the thing it *asserts
about* lives, not where its filename points.

**To repo 1** — pivot, scribe, clear, depth, rise, stencil, indexer,
grabber and czcore internals: `test_aspect`, `test_solver`,
`test_tracking`, `test_scribe_exports`, `test_scribe_tighten`,
`test_clear_dsp`, `test_denoise`, `test_depth`, `test_rise_engine`,
`test_stencil_post`, `test_indexer`, `test_shots`, `test_media`,
`test_models`, `test_export_presets`, `test_fcpxml`, `test_fusion`,
`test_jobs`, `test_drain`, `test_proxy_captions`, `test_mt_local`,
`test_vision_local`, `test_fetch_tools`.

**To repo 2** — everything memory, record, web, highlighter, publisher,
interpreter, narrator and suite.

**The traps, by name:**

- `test_slate.py` is named for a repo-1 package and imports
  `publisher.brand` and `suite.tools.slate`. It is a repo-2 test wearing a
  repo-1 name. It goes to repo 2, and the `slate/` package itself has no
  test on the other side until someone writes one.
- `test_index_desk.py` and `test_grabber_desk.py` test the *suite pages*
  for repo-1 tools. Repo 2.
- `test_kb.py`, `test_frames.py`, `test_davinci.py` name nothing and import
  `suite`. Repo 2.
- `test_llm_names.py` spans czcore and highlighter. Repo 2, which has both.
- `test_packaging.py` imports nothing at all and shells out at a built app.
  Repo 2.
- `test_interpreter_mt.py` imports only `czcore` but asserts about
  Interpreter's translation. Repo 2.

**The rule that follows:** repo 2 may test across the seam, because it has
repo 1 installed. Repo 1 may never test across it, ever, because that
import would recreate the cycle the split removes. Enforce it with the same
grep from §1, run in CI.

**And one promise breaks.** `requirements.txt` says the core algorithm tests
need nothing but stdlib, and `python3 -m unittest discover -s tests -t .`
works today in a bare checkout because `-t .` puts the repo root on
`sys.path` and every package is right there. After the split, repo 2's test
run needs repo 1 installed first. Repo 1 keeps the bare-checkout promise;
repo 2 loses it, and its README must say so rather than let someone
discover it as an ImportError.

**685 tests** is a number that stops being true on both sides
simultaneously. Neither repo can claim it. CHANGELOG entries citing it are
historical and should be left alone, not retconned.

### `packaging/` and the DMG

Goes to repo 2 entire — it builds Civic Media Studio.app, bundle identifier
`org.civicmedia.studio`, and 2.0.0 is notarized under it.

Beyond the `suite.spec` edits in §3:

- **`NOTICE` forks, and neither copy is a subset.** The bundled LGPL FFmpeg,
  libsndfile, the interpreter glossaries and the relink note belong to repo
  2 — that is the DMG's bill. The model registry is `czcore/models.py`,
  which is repo 1, and the models are pulled by tools on both sides. Repo 1
  carries the model list; repo 2's NOTICE names the bundled natives and
  *references* repo 1's list rather than duplicating it, because a
  duplicated list is a list that will disagree with itself by March. The
  DMG must ship both texts. The 1.9.0 audit caught a DMG carrying no LGPL
  text at all; a split is exactly the kind of shuffle that reintroduces
  that.
- **Repo 1 gets no packaging story**, and that is a decision worth stating:
  the nine tools reach Resolve users through the suite DMG or through pip.
  Which means control-z.org — the sub-brand's own site — distributes the
  parent's binary. Slightly awkward, already true today, not made worse by
  the split.

### `.claude/`

**This is the most likely thing to be silently lost.** `.claude/` is in
`.gitignore`. Nothing in any git operation carries it. `branding.md` — the
authoritative brand rules, the token sheet, the volume law — exists on this
Mac and nowhere else in version control.

Un-ignore and commit `.claude/rules/branding.md` **before** the split, in
the monorepo, so both repos inherit it through the normal mechanisms. Then
split it: repo 1 needs the Control-Z and civicmedia sections; repo 2 needs
all four brands. Do not thin repo 1's copy too aggressively — Control-Z is
a sub-brand and cannot be styled without the parent's rules beside it.

`launch.json` is already stale and will get worse. Every path in it is
absolute (`/Users/amateurmenace/control-z/...`), so both repos need their
own with new roots — and one configuration still names `studio.app:app`,
a module that was renamed to `record/` and does not exist. Fix it while
you are in there.

`.claude/worktrees/` holds two checkouts of an older tree — no `record/`,
still carrying `Start control-z Suite.command`. Prune them before the
split. A filter-repo run aimed at the wrong directory is a bad afternoon.

### CHANGELOG

1396 lines, one file, two products interleaved since the first release. The
suite releases v1.0.0 through 2.0.0 all contain tool work.

**Do not split it.** Deciding, bullet by bullet, which product each of 1396
lines belonged to is a week of judgement calls that produces two plausible
fictions instead of one true document. The histories genuinely were one.

Copy it verbatim into both repos, and in each add four lines at the top
saying that everything below the split date describes a single repository,
naming the archive and the pre-split tag. Each repo's own numbering starts
after.

**Version numbers.** Repo 2 keeps 2.0.0 — the bundle identifier and the
notarized build already carry it. Repo 1 should also start at **2.0.0**
rather than resetting to 1.0.0: the shared history justifies the shared
number, and a repository whose release notes go v1.9.0, 2.0.0, v1.0.0 needs
a paragraph of explanation on every page it appears. Repo 1's inherited
tags are dropped in the extraction, so there is no collision.

### `specs/`

Numbered 00–18 and referenced by number in twelve commit messages, in
`PARALLEL.md`, in `NOTICE`, and throughout both codebases' prose.

**Renumber nothing.** Copy the whole directory into both repositories,
delete nothing on either side. 00–17 are finished documents; duplicating
them costs a few hundred kilobytes and preserves every reference. Each repo
adds a short `specs/README.md` naming which specs are live there and which
are inherited context:

- **Live in repo 1:** 01 pivot, 02 stencil, 03 scribe, 04 clear, 05 rise,
  06 depth, 10 template pack, and the grabber/indexer/slate half of 11.
- **Live in repo 2:** 07 site, 08 suite, 09 packaging, 12–15 the community
  program, 16 web, 17 studio, and the highlighter half of 11.
- **Both:** 00 overview, 18 this document, PARALLEL.md.

They will drift. Accept it; they are historical.

### gh-pages and control-z.org

`gh-pages` currently serves control-z.org from `site/docs`, and it carries
`app/` — the record's static edition, which `web/bake.py` writes there by
default (`--out site/docs/app`). So publicrecord's reader is served under
Control-Z's domain by repo 2's baker.

Brand architecture says control-z.org belongs to repo 1. Practice says
`site/` and gh-pages must stay with repo 2, at least for now, because the
thing that writes into them lives there.

**Do not migrate the domain in the same operation.** This CHANGELOG already
made the argument better than I can: a resident who cited a timestamp in
June should not find a 404 in July. control-z.org/app is a live URL with
216 issue pages and deep links behind it. One risky thing at a time. `site/`
and gh-pages stay in repo 2; the migration is its own spec, its own week,
and its own redirect map.

### Project memory

`~/.claude/projects/-Users-amateurmenace-control-z/memory/` — eleven
entries, keyed by project *directory path*. Both new checkouts are new
paths. Both start empty; the existing index strands where nothing will look
for it.

Copy the directory into both new project paths by hand before the first
session in either, then prune each side and rewrite `MEMORY.md`'s index.
Several entries become false on one side: "the two Macs hold different
corpora" is repo 2's; the spctl loaner gate is repo 2's DMG; the v1.x
release entries cite SHAs that survive in repo 2 and die in repo 1.

### The two Macs, and PARALLEL.md's lane law

Two Macs, two repositories: four checkouts, four venvs, and a pin between
two of them.

**The hard gate: every lane branch must be merged or abandoned before the
split begins.** A lane branch that outlives the split cannot be merged
afterward, because its commits span a boundary that no longer exists.
Today `git branch -a --no-merged main` shows only `gh-pages` and
`backup/local-main-pre-1.5.0-20260717`, and the four lane branches are all
merged. Verify again on the day, from both Macs, after `git fetch --all
--prune`.

Half of PARALLEL.md's law gets enforced by the repository boundary itself,
which is better than a document — "`czcore/` is A's, B imports and never
edits" becomes structurally true. The other half gets worse. **31 of 143
commits touched both sides.** After the split each of those is two commits
in two repositories, a tag, and a pin bump. That is the ongoing tax and it
is the real price of this split.

The second Mac's warning — different corpora, never rebake the public
edition there — currently lives only in project memory. Write it into repo
2's own docs during the split, because project memory is the thing least
likely to survive it.

---

## 5. The runbook

Every step names its rollback. A split that cannot be reversed on day two
is not a migration, it is a bet.

### 0 — Freeze

Announce a merge freeze on both Macs. Then, on both:

```sh
git fetch --all --prune
git status --porcelain          # must be empty
git branch -a --no-merged main  # must be gh-pages and the backup only
git push origin main
```

*Rollback:* nothing has changed.

### 1 — Tag the seam

```sh
git tag -a pre-split -m "The last commit of the monorepo. Repo 1 is
extracted from here; repo 2 continues from here."
git push origin pre-split
```

Every rollback below returns to this tag, and both repositories cite it.

*Rollback:* `git tag -d pre-split && git push --delete origin pre-split`

### 2 — Mirror the archive, twice

```sh
git clone --mirror https://github.com/amateurmenace/control-z.git \
  /Volumes/<drive>/archive/control-z-monorepo.git
git clone --mirror https://github.com/amateurmenace/control-z.git \
  ~/Archive/control-z-monorepo.git
```

78 MB. Do not skip this because the GitHub copy exists; step 8 edits the
GitHub copy.

*Rollback:* n/a.

### 3 — Rescue what git does not carry

```sh
git rm --cached .gitignore && :   # then edit: drop the bare `.claude/` line
mkdir -p .claude/rules
git add -f .claude/rules/branding.md
git commit -m "The brand rules join the repository, before they can be lost
in the split"
git push origin main

cp -R ~/.claude/projects/-Users-amateurmenace-control-z/memory \
  ~/Archive/control-z-project-memory
rm -rf .claude/worktrees/recursing-hodgkin-eb30c7 \
       .claude/worktrees/suspicious-feynman-eb27a9
```

Keep ignoring `.claude/settings.local.json` and `.claude/worktrees/`; it is
only the rules that must survive.

*Rollback:* `git revert` the commit. The copied memory directory is inert.

### 4 — Extract repo 1

From a **fresh** clone, with the remote removed. `git filter-repo` refuses
to run on a clone with an origin unless forced; honor the refusal, it is
there to stop exactly the accident you are about to not have.

```sh
mkdir -p /tmp/split && cd /tmp/split
git clone https://github.com/amateurmenace/control-z.git control-z-tools
cd control-z-tools
git remote remove origin

git filter-repo \
  --path czcore/ --path pivot/ --path stencil/ --path scribe/ \
  --path clear/  --path rise/  --path depth/   --path grabber/ \
  --path slate/  --path indexer/ \
  --path grades/ --path packs/ \
  --path specs/ \
  --path tests/ \
  --path LICENSE --path .gitignore --path CHANGELOG.md \
  --path .claude/rules/branding.md
```

`specs/` and `tests/` come across whole and are pruned in step 5 by hand,
because pruning them here means naming 56 test paths in a filter expression
and getting one wrong silently.

Then drop the inherited tags — they were suite releases:

```sh
git tag | xargs -r git tag -d
```

*Rollback:* `rm -rf /tmp/split/control-z-tools`. Nothing upstream was
touched.

### 5 — Give repo 1 its own skin

Still local, still no remote. Working from `/tmp/split/control-z-tools`:

- **`pyproject.toml`** — new: `name = "control-z"`, `version = "2.0.0"`,
  `license = { text = "MIT" }`, the nine CLI entry points, `packages`
  listing only the ten packages, and `package-data` for
  `depth/templates/*.setting` and `pivot/static/*.html`. Declare **real
  dependencies** this time rather than an empty list plus a
  `requirements.txt` — see §3.
- **`README.md`** — rewritten for the tools alone, naming the archive tag
  and linking repo 2.
- **`NOTICE`** — the model registry and its licences. Drop the bundled-
  native section; that is repo 2's DMG.
- **`CHANGELOG.md`** — verbatim, with the four-line split header.
- **`tests/`** — delete the repo-2 tests per §4, including the traps.
- **`specs/`** — keep all of them, add `specs/README.md`.
- **`LICENSE`** — untouched.
- One commit: `git commit -am "The tools, extracted"`.

Then prove it in a clean venv:

```sh
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -t .
grep -rnE '(from|import) (brand|memory|web|record|highlighter|publisher|interpreter|narrator|suite)\b' \
  czcore pivot stencil scribe clear rise depth grabber slate indexer --include='*.py'
```

The grep must return nothing. That is the acceptance test for the whole
split, not a formality.

*Rollback:* `git reset --hard`, or delete the directory.

### 6 — Create repo 1 on GitHub, and push

**First irreversible-ish step.** A pushed public repository can be deleted,
but anything cloned between push and delete is out in the world.

Create `amateurmenace/control-z-tools`, empty, MIT.

```sh
git remote add origin https://github.com/amateurmenace/control-z-tools.git
git push -u origin main
git tag -a v2.0.0 -m "The tools, on their own" && git push origin v2.0.0
```

**On the name.** Repo 1's brand is control-z.org, and `control-z` is the
slug it wants. It cannot safely have it. If repo 2 is renamed away from
`control-z`, GitHub leaves a redirect — and creating a new repository under
the freed name *silently kills that redirect*, so every existing clone URL,
every bookmark, every CI reference pointing at `amateurmenace/control-z`
starts resolving to a repository with no `suite/` in it. That is worse than
a 404, because it fails at import time in someone else's build rather than
at fetch time in front of you. Take `control-z-tools`, leave the redirect
alone, and accept that the slug does not match the brand. This is a
judgement call and Stephen may weigh it differently — but if he takes the
name, the redirect must be broken deliberately and announced, not
discovered.

*Rollback:* delete the GitHub repository. Deletion is not retraction.

### 7 — Fix the pin

Repo 2 will depend on `git+https://github.com/amateurmenace/control-z-tools@v2.0.0`.
Nothing to publish. Do not upload to PyPI on day one (§3).

*Rollback:* n/a — a tag is all that exists.

### 8 — Turn the monorepo into repo 2, on a branch

```sh
cd ~/control-z
git switch -c split/repo2
git rm -r --quiet czcore pivot stencil scribe clear rise depth \
                  grabber slate indexer grades packs
```

Then, in one or a few commits:

- **`LICENSE`** — replaced with AGPL-3.0 verbatim, copyright line preserved.
- **`pyproject.toml`** — `name`, `license = { text = "AGPL-3.0-only" }`,
  the git-URL dependency, `packages` minus the ten, `[project.scripts]`
  minus the repo-1 CLIs (`pivot-cli`, `stencil-cli`, `scribe-cli`,
  `clear-cli`, `rise-cli`, `depth-cli`, `grabber-cli`, `index-cli`,
  `slate-cli` all leave; `suite`, `highlighter-cli`, `publisher-cli` stay).
- **`requirements.txt`** — the repo-1 dependencies leave with repo 1; what
  remains is what repo 2 adds on top. Rewrite the header comment, which
  currently says "all six tools".
- **`packaging/suite.spec`** — the `collect_data_files` change from §3.
- **`packaging/build_suite.sh`** — the editable-install gate from §3.
- **`NOTICE`** — the bundled natives, referencing repo 1's model list.
- **`README.md`, `CHANGELOG.md`** header, `specs/README.md`.
- **`tests/`** — delete the repo-1 tests.
- **`.claude/launch.json`** — and fix `studio.app:app` → `record.app:app`.
- **`Start Civic Media Studio.command`** — check that first-run pip picks up
  the git dependency, which now needs `git` and a network on first launch
  where before it needed only PyPI. This is a real regression in the
  double-click story and may on its own be the argument for Phase 2.

*Rollback:* `git switch main && git branch -D split/repo2`. Fully
reversible, which is exactly why it is a branch and not a commit on main.

### 9 — Prove it, and the DMG is the proof

```sh
rm -rf .venv && python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install .
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python -m suite --serve       # click through all eight desk pages
bash packaging/build_suite.sh
```

Then **diff the built tree against the notarized 2.0.0 build**:

```sh
cd packaging/dist && find "Civic Media Studio.app" -type f | sort > /tmp/after.txt
# compare against the 2.0.0 manifest from its release notes
diff /tmp/before.txt /tmp/after.txt
```

A difference is a finding, not a formality. The whole point of the split is
that it changes where the code lives and not what it is; if the app's file
list moved, something in §3 is wrong and you want to know now.

*Rollback:* same as step 8.

### 10 — Land it

```sh
git switch main && git merge --no-ff split/repo2
git push origin main
```

Then rename the repository on GitHub to `civicmedia-studio` and update the
remote on both Macs. **Do not touch `gh-pages` or the CNAME** (§4).

*Rollback:* `git revert -m 1 <merge>`, and rename the repository back —
GitHub allows it and the redirect follows.

### 11 — Re-seed both Macs

Fresh clones of both repositories on both machines. Fresh venvs. Copy
`.claude/settings.local.json` and the archived project memory into each of
the four project paths, prune each, rewrite each `MEMORY.md` index.
Restate the different-corpora warning in repo 2's own docs.

*Rollback:* n/a.

### 12 — Release from each, and verify the seal

Cut repo 2's next DMG through the full chain and confirm notarization still
passes. The bundle identifier and the signing identity did not change, so
it should. "Should" is not "did", and the spctl loaner gate is still un-run
from 1.9.0 — this is the moment to finally run it.

---

## 6. What not to do

1. **Do not `git filter-repo` the monorepo itself.** Repo 2 keeps its SHAs.
   Rewriting them orphans every tag, every release asset, the seven
   gh-pages deploy commits, and every SHA cited in CHANGELOG, release notes
   and project memory — to gain nothing, because repo 2 is already almost
   exactly what filter-repo would produce.
2. **Do not delete the monorepo.** It is the archive of record and it is
   where the tools' blame keeps its original shape.
3. **Do not `pip install -e ../control-z` into a release venv.** Twice
   already: v1.1 shipped against a stale editable install, and 1.9.0 nearly
   shipped a Suite whose pypdf existed only as a hiddenimport. Gate it in
   `build_suite.sh` and assert it in the tests.
4. **Do not change the bundle identifier.** `org.civicmedia.studio` is what
   2.0.0 was notarized as. Change it and the post-split build installs
   *beside* the app users already have — that cost was paid once, on
   purpose, for a rename that had a reason. This split has no reason; it
   should be invisible to macOS as it is to users.
5. **Do not re-sign with a fresh identity "to be safe,"** and do not accept
   a DMG whose file list differs from 2.0.0's without explaining every line
   of the difference.
6. **Do not reuse the GitHub slug `control-z` for repo 1** while the
   rename redirect is live (§5.6).
7. **Do not renumber `specs/`.** Twelve commit messages reference specs by
   number and cannot be edited.
8. **Do not split the CHANGELOG line by line.** Two plausible fictions are
   worse than one true document.
9. **Do not migrate control-z.org or move `/app` in the same operation.**
   Live deep links, 216 issue pages, residents who were told to cite them.
10. **Do not vendor repo 1 into repo 2 as a subtree**, not even "just for
    the build". Two copies of the tools is the failure PARALLEL.md was
    written to prevent, back when it was a lane law and not a repository
    boundary.
11. **Do not squash repo 1's extraction to a single commit *and* let the
    archive go.** Either alone is survivable. Both together is amnesia.

---

## 7. Where I think this is wrong

Two things, stated once and not relitigated.

**The tax is real and it is paid forever.** 31 of 143 commits crossed the
seam. That rate will fall — much of it was the community wing landing all at
once — but it will not fall to zero, and every one that remains becomes two
commits in two repositories, a tag, and a pin bump. The split is worth that
only if repo 1's surface actually stabilizes. If in three months the pin is
still moving weekly, then the split bought a licence line at the price of a
release train, and the honest alternative was always available: **one
repository with per-directory LICENSE files.** A repository may lawfully
contain code under two licences; `LICENSE` at the root, `czcore/LICENSE`
and friends under MIT, and a NOTICE that says which is which. That is
legally sufficient and costs nothing per commit. It is uglier and it is
weaker as a signal to Resolve users that the tools are theirs. The decision
to split is made; this is only the note that says what it cost.

**The licence line may be drawn one directory too wide.** specs/17 §9 says
"AGPL-3.0 on `record/`" — not on the suite. AGPL's network clause bites the
hosted thing, and the hosted thing is `record/` and `web/`. `suite/`,
`packaging/`, `highlighter/`, `publisher/`, `interpreter/` and `narrator/`
are desktop software, where §13 is exactly as inert as it is for the nine
tools that are leaving under MIT precisely because it is inert there. If
inertness is the argument for MIT on the tools, it is the same argument for
MIT on the desk. Putting the whole civic stack under AGPL is a stronger
claim than specs/17 makes, and it may be the right one — copyleft as a
statement rather than a mechanism is a legitimate choice — but it should be
made on purpose rather than inherited from the repository boundary. It is
listed as an open question below, not as an objection.

---

## 8. Open questions

1. **Is AGPL right for the whole civic stack, or only for `record/` and
   `web/`?** specs/17 §9 asserts the narrower claim. §7 above.
2. **AGPL ratification itself is still open** — specs/12 §9 lists it as
   blocking In-a-Box Phase 1, together with the muni-IT note. This spec
   assumes ratification; it does not perform it, and the corresponding-
   source question for a signed app bundling a pinned MIT dependency is a
   lawyer's, not mine.
3. **Which repository owns control-z.org, and when?** Brand says repo 1.
   `web/bake.py` writes into `site/docs/app` and gh-pages serves it, so
   practice says repo 2. Deferred deliberately; needs its own spec and a
   redirect map for the 216 issue pages.
4. **The GitHub slug for repo 1.** `control-z-tools` is safe;
   `control-z` matches the brand and requires deliberately breaking a
   rename redirect. Stephen's call (§5.6).
5. **Is `control-z` available on PyPI**, and under what distribution name
   should repo 1 eventually publish? Unchecked. Blocks Phase 2 of §3, not
   day one.
6. **What does the first-run experience become?** `Start Civic Media
   Studio.command` now needs `git` on the user's machine to resolve a git
   URL dependency. On a fresh Mac, `git` means the Xcode command-line tools
   prompt. That may be the single strongest argument for going to PyPI
   sooner than §3 recommends.
7. **Does repo 1 need its own release artifact at all** — a DMG, a Resolve
   installer — or does it live only inside the parent's app and on PyPI?
   Today it has none, and control-z.org distributes repo 2's binary.
8. **The `brand/` divergence.** `web/emit.py` inlines the publicrecord mark
   by hand instead of reading `brand/logos/`, and no Python anywhere
   imports the `brand` package. It is a data directory with a
   `__init__.py`. Worth resolving, but not by this spec and not on split
   day.
9. **Control-Z still has no keycap mark** (branding.md's standing TODO).
   The split makes it more visible, not less: repo 1 is about to have its
   own README, its own PyPI page, and no logo.
