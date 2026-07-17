"""Packaging gates: GPL linkage, one-FFmpeg rule, freeze resource contracts.

specs/09 §3: `otool -L` is the only license authority — avcodec_license() and
PyPI metadata both report non-GPL for wheels that physically link libx264.
These tests sweep the load commands of everything that would ship. They are
macOS-only by nature (otool) and skip cleanly elsewhere, like the pipeline
tests do.
"""

import pathlib
import re
import subprocess
import shutil
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]

# GPL libraries that must never appear in a load command of anything shipped.
# libpostproc only exists under --enable-gpl, so it doubles as a witness that
# a foreign (GPL-configured) FFmpeg sneaked in.
GPL_PATTERNS = ("x264", "x265", "libpostproc", "libvidstab", "libxvid")

HAVE_OTOOL = shutil.which("otool") is not None


def _site_packages() -> pathlib.Path:
    for p in sys.path:
        pp = pathlib.Path(p)
        if pp.name == "site-packages" and pp.is_dir():
            return pp
    raise AssertionError("no site-packages on sys.path")


def _shipped_trees():
    """The native trees a frozen app would carry (present subset thereof)."""
    sp = _site_packages()
    candidates = [
        sp / "av",
        sp / "cv2",
        sp / "onnxruntime",
        sp / "ctranslate2",
        sp / "sherpa_onnx",
        sp / "_soundfile_data",
        REPO / "packaging" / "vendor" / "ffmpeg" / "lib",
        REPO / "packaging" / "vendor" / "ffmpeg" / "bin",
    ]
    return [c for c in candidates if c.exists()]


def _machos(tree: pathlib.Path):
    for f in tree.rglob("*"):
        if f.is_symlink() or not f.is_file():
            continue
        if f.suffix in (".so", ".dylib") or (f.parent.name == "bin" and f.stat().st_mode & 0o111):
            yield f


def _load_commands(macho: pathlib.Path) -> str:
    out = subprocess.run(["otool", "-L", str(macho)],
                         capture_output=True, text=True)
    return out.stdout


def _referenced_paths(macho: pathlib.Path):
    """Install-name references of a Mach-O, resolved where we can.

    @loader_path resolves relative to the Mach-O's own directory; absolute
    paths pass through. @rpath and unresolvable forms return None alongside
    the raw line so callers can still pattern-match the text.
    """
    out = []
    for line in _load_commands(macho).splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        ref = line.split(" (compatibility")[0].strip()
        resolved = None
        if ref.startswith("/"):
            resolved = pathlib.Path(ref)
        elif ref.startswith("@loader_path/"):
            resolved = macho.parent / ref[len("@loader_path/"):]
        out.append((ref, resolved))
    return out


@unittest.skipUnless(HAVE_OTOOL, "otool not available (macOS-only gate)")
class TestGPLLinkage(unittest.TestCase):
    def test_no_gpl_library_anywhere(self):
        """The build gate specs/09 §3 mandates: fail on any x264/x265 match.

        Two integrity rules, both from adversarial review of this very test:
        (1) the sweep must PROVE it swept something — an empty tree list or a
        site-packages layout shift must fail, not pass green; (2) it follows
        one level of out-of-tree references, so a libavcodec living outside
        the swept trees can't smuggle in a transitive x264 link.
        """
        trees = _shipped_trees()
        self.assertTrue(any(t.name == "av" for t in trees),
                        "the av package is not among the swept trees — the "
                        "sweep would be vacuous")
        offenders, checked = [], 0
        outside = set()
        for tree in trees:
            for macho in _machos(tree):
                checked += 1
                for ref, resolved in _referenced_paths(macho):
                    if any(pat in ref for pat in GPL_PATTERNS):
                        offenders.append(f"{macho}: {ref}")
                    if (resolved is not None and resolved.is_file()
                            and not any(str(resolved).startswith(str(t))
                                        for t in trees)):
                        outside.add(resolved)
        # one level of transitive follow for out-of-tree libraries
        for lib in outside:
            for ref, _ in _referenced_paths(lib):
                if any(pat in ref for pat in GPL_PATTERNS):
                    offenders.append(f"(transitive) {lib}: {ref}")
        self.assertGreater(checked, 20,
                           f"only {checked} Mach-O files swept — the gate "
                           "has lost its inputs and cannot be trusted")
        self.assertEqual(offenders, [],
                         "GPL libraries linked by shipped binaries:\n"
                         + "\n".join(offenders))

    def test_exactly_one_ffmpeg(self):
        """Two FFmpegs collide at the ObjC runtime (duplicate AVFFrameReceiver
        — an observed warning and a latent nondeterministic crash). Every
        libavcodec reference in the shipped trees must agree on one major."""
        majors = set()
        seen_refs = 0
        for tree in _shipped_trees():
            for macho in _machos(tree):
                for ref, _ in _referenced_paths(macho):
                    m = re.search(r"libavcodec\.(\d+)", ref)
                    if m:
                        majors.add(m.group(1))
                        seen_refs += 1
        self.assertGreater(seen_refs, 0,
                           "no libavcodec reference found anywhere — av is "
                           "missing or the sweep is broken")
        self.assertEqual(
            len(majors), 1,
            f"multiple FFmpeg majors reachable: {sorted(majors)} — "
            "the second one usually rides in via the cv2 wheel")

    def test_av_is_our_build_when_vendor_exists(self):
        """Once packaging/vendor/ffmpeg exists, av must link against it —
        a PyPI-wheel av (with its .dylibs dir) means someone reinstalled."""
        vendor = REPO / "packaging" / "vendor" / "ffmpeg"
        if not vendor.exists():
            self.skipTest("vendor FFmpeg not built on this machine")
        sp = _site_packages()
        self.assertFalse(
            (sp / "av" / ".dylibs").exists(),
            "av/.dylibs exists — that is the PyPI wheel (GPL x264/x265), "
            "not the sdist build; run packaging/build_pyav.sh")


class TestFreezeResourceContract(unittest.TestCase):
    """The --add-data destinations specs/09 §5 verified: source trees must
    stay where the spec file maps them from, or the frozen app loses them."""

    def test_suite_static_exists(self):
        self.assertTrue((REPO / "suite" / "static" / "app.css").exists())

    def test_depth_templates_exist(self):
        # The freeze contract is "the template directory ships, populated" —
        # the exact count belongs to the template-pack spec (specs/10 grew it
        # from five to ten mid-flight and rightly broke a hardcoded 5 here).
        settings = list((REPO / "depth" / "templates").glob("*.setting"))
        self.assertGreaterEqual(len(settings), 5,
                                "depth's Fusion template pack looks gutted")
        for s in settings:
            self.assertGreater(s.stat().st_size, 0, f"empty template: {s.name}")


if __name__ == "__main__":
    unittest.main()
