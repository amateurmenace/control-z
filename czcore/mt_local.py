"""A local machine-translation runtime — the last API door for Interpreter.

Interpreter's quality path is the user's own key (czcore.llm). This module is
the *local* alternative: a CTranslate2 model (NLLB-200 / MADLAD class) run
entirely on-device, so the seven panel languages need no key and spend no
tokens. It slots in behind ``czcore.mt.available()`` exactly the way the local
TTS voice slots in behind ``czcore.tts.available()`` — discovered by the shape
of a directory in the shared model store, never bundled.

**Discovery by shape, not a bundled model.** A CT2 translation model is a
directory holding ``model.bin`` plus a tokenizer (``sentencepiece.bpe.model``
or ``tokenizer.json``). This module finds the first such directory under
``models_dir()/mt/`` and uses it. Nothing here downloads a model — the operator
installs one they've chosen, and its license is their decision (NLLB-200 is
CC-BY-NC-4.0, non-commercial; MADLAD-400 is Apache-2.0 — the covenant's
permissive-only rule for *shipped* models means the project does not press a
non-commercial card into the signed app; the mechanism is here, the model is
the steward's call). The status line says exactly which model is running.

**The N| adapter.** Rather than re-implement the whole cue pipeline, this
exposes a ``complete``-shaped adapter that ``mt.translate_cues`` already knows
how to drive: it receives the numbered ``k|text`` block, translates each line,
and returns ``k|out`` lines — so every fallback, miss-detection, timing and
provenance guarantee in mt.py holds unchanged. A line the model can't carry
falls back to English, honestly, the same as the key path.

Glossary do-not-translate terms are protected by placeholder substitution
(the local engine can't read a prompt), then restored — and ``mt.check_kept``
still runs downstream as the honest miss detector.

Stdlib-only at import time, per the house dep-guard convention — ctranslate2
and the tokenizer import lazily inside functions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List, Optional

# panel code -> FLORES-200 code (NLLB's target identity). 'simple' has no NLLB
# target — Simple English is an intralingual rewrite, so the local engine
# declines it and it stays on the key path (or honestly unavailable).
FLORES = {
    "en": "eng_Latn", "es": "spa_Latn", "zh": "zho_Hans", "pt": "por_Latn",
    "ht": "hat_Latn", "vi": "vie_Latn", "ru": "rus_Cyrl",
}
SRC = "eng_Latn"

_TRANSLATOR = {}     # model dir -> (Translator, tokenizer) — loaded once


def _mt_root(root: Optional[Path] = None) -> Path:
    from . import models
    return (root or models.models_dir()) / "mt"


def _model_dirs(root: Optional[Path] = None) -> List[Path]:
    """Directories under models_dir()/mt/ that look like a CT2 model: a
    model.bin beside a tokenizer. Sorted, so the choice is stable."""
    base = _mt_root(root)
    if not base.is_dir():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        if (d / "model.bin").exists() and (
                (d / "sentencepiece.bpe.model").exists()
                or (d / "tokenizer.json").exists()
                or (d / "shared_vocabulary.txt").exists()):
            out.append(d)
    return out


def model_name(root: Optional[Path] = None) -> Optional[str]:
    dirs = _model_dirs(root)
    return dirs[0].name if dirs else None


def available(root: Optional[Path] = None) -> dict:
    """{engine, model, sentence} in mt.available()'s vocabulary. engine is
    'local' when a CT2 model is installed AND ctranslate2 imports, else None."""
    dirs = _model_dirs(root)
    if not dirs:
        return {"engine": None, "model": None,
                "sentence": "no local translation model installed — place a "
                            "CTranslate2 model (model.bin + a tokenizer) in a "
                            "folder under the suite's models/mt/ directory "
                            "(MADLAD-400 is Apache-2.0; NLLB-200 is CC-BY-NC — "
                            "the operator's licence call)"}
    try:
        import ctranslate2  # noqa: F401
    except Exception:
        return {"engine": None, "model": None,
                "sentence": "a local translation model is installed but "
                            "ctranslate2 isn't available in this environment"}
    name = dirs[0].name
    return {"engine": "local", "model": name,
            "sentence": f"translation runs on-device — {name}, no key, no tokens"}


def _load(root: Optional[Path] = None):
    """(Translator, tokenizer) for the first installed model, cached. The
    tokenizer is either a sentencepiece .model or a HF fast tokenizer.json."""
    dirs = _model_dirs(root)
    if not dirs:
        raise RuntimeError("no local translation model installed — "
                           "drop a CTranslate2 model under the models folder")
    d = dirs[0]
    key = str(d)
    if key in _TRANSLATOR:
        return _TRANSLATOR[key]
    import ctranslate2
    translator = ctranslate2.Translator(str(d), device="cpu",
                                        compute_type="int8")
    tok = _load_tokenizer(d)
    _TRANSLATOR[key] = (translator, tok)
    return _TRANSLATOR[key]


def _load_tokenizer(d: Path):
    """A tokenizer object exposing encode(text)->tokens and
    decode(tokens)->text over NLLB's subword vocabulary. Prefers the HF fast
    tokenizer (tokenizer.json, no sentencepiece dep); falls back to a raw
    sentencepiece model."""
    tj = d / "tokenizer.json"
    if tj.exists():
        from tokenizers import Tokenizer
        hf = Tokenizer.from_file(str(tj))
        return _HFTok(hf)
    spm = d / "sentencepiece.bpe.model"
    if spm.exists():
        try:
            import sentencepiece as spmlib
        except ImportError:
            # the suite deliberately doesn't ship sentencepiece — reaching
            # this path means someone installed a model folder by hand, and
            # they deserve the real sentence, not a bare ModuleNotFoundError
            raise RuntimeError(
                "this model uses a sentencepiece tokenizer the suite doesn't "
                "ship — prefer a model that carries tokenizer.json, or "
                "pip install sentencepiece in the suite's venv")
        sp = spmlib.SentencePieceProcessor()
        sp.load(str(spm))
        return _SPTok(sp)
    raise RuntimeError("the local translation model has no readable tokenizer")


class _HFTok:
    def __init__(self, hf):
        self.hf = hf

    def encode(self, text: str) -> List[str]:
        return self.hf.encode(text).tokens

    def decode(self, tokens: List[str]) -> str:
        ids = [self.hf.token_to_id(t) for t in tokens
               if self.hf.token_to_id(t) is not None]
        return self.hf.decode(ids)


class _SPTok:
    def __init__(self, sp):
        self.sp = sp

    def encode(self, text: str) -> List[str]:
        return self.sp.encode(text, out_type=str)

    def decode(self, tokens: List[str]) -> str:
        return self.sp.decode(tokens)


# -- glossary placeholder protection (the local engine can't read a prompt) --

_PH = "␞{}␞"       # a record-separator-fenced token unlikely in text


def _protect(text: str, keep: List[str]):
    holds = {}
    out = text
    for i, term in enumerate(sorted(set(t for t in keep if t), key=len,
                                    reverse=True)):
        ph = _PH.format(i)
        pat = re.compile(re.escape(term), re.I)
        if pat.search(out):
            out = pat.sub(ph, out)
            holds[ph] = term
    return out, holds


def _restore(text: str, holds: dict) -> str:
    for ph, term in holds.items():
        text = text.replace(ph, term)
    return text


def translate_lines(texts: List[str], code: str,
                    keep: Optional[List[str]] = None,
                    root: Optional[Path] = None) -> List[str]:
    """Translate a batch of English lines into `code` (a panel code). Returns
    one output per input, in order; a line that can't be carried comes back
    empty (the caller falls it back to English). Raises RuntimeError for an
    unsupported code or an unusable model."""
    tgt = FLORES.get(code)
    if not tgt:
        raise RuntimeError(f"the local engine can't translate “{code}”")
    keep = list(keep or [])
    translator, tok = _load(root)
    holds_all, srcs = [], []
    for t in texts:
        protected, holds = _protect(t, keep)
        holds_all.append(holds)
        # NLLB source-language tag prefixes the token stream
        srcs.append([SRC] + tok.encode(protected))
    res = translator.translate_batch(
        srcs, target_prefix=[[tgt]] * len(srcs),
        beam_size=1, max_batch_size=16)
    out = []
    for i, r in enumerate(res):
        toks = list(r.hypotheses[0])
        # drop the forced target-language tag before decoding
        if toks and toks[0] == tgt:
            toks = toks[1:]
        try:
            text = tok.decode(toks)
        except Exception:
            text = ""
        out.append(_restore(text, holds_all[i]).strip())
    return out


def adapter(code: str, glossary: Optional[dict] = None,
            root: Optional[Path] = None) -> Callable:
    """A ``complete``-shaped function mt.translate_cues can drive: it parses the
    numbered ``k|text`` block, translates each line locally, and returns
    ``k|out`` lines. Reuses every fallback/miss/timing guarantee in mt.py."""
    keep = list((glossary or {}).get("keep") or [])

    def complete(prompt: str = "", system: str = "", max_tokens: int = 0):
        rows = []
        for ln in prompt.splitlines():
            if "|" not in ln:
                continue
            k, text = ln.split("|", 1)
            k = k.strip()
            if k.isdigit():
                rows.append((k, text))
        if not rows:
            return ""
        outs = translate_lines([t for _, t in rows], code, keep=keep, root=root)
        return "\n".join(f"{k}|{o}" for (k, _), o in zip(rows, outs) if o)

    return complete
