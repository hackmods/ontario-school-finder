"""Languages. English is the source text everywhere; French comes from catalogue fragments in
site/i18n/fr/*.json (English source string -> French), one fragment per template or script, all merged.

    _("Find a school")                          plain text (Jinja escapes it)
    _("Schools in postal area {fsa}", fsa=x)    named placeholders, filled after translating
    _h("Read <a href=\"{url}\">the guide</a>", url=x)  trusted markup from our own catalogue; arguments escaped
    u("/school/123/")                           a site link in the current language (/fr/... for French)

A missing French string falls back to English and is recorded, so a build reports what is left to translate
(site/i18n/missing-fr.txt) instead of failing. The French version is a machine translation, not reviewed:
every French page says so and links the English page, which is the reference.
"""
from __future__ import annotations

import json
from pathlib import Path

from markupsafe import Markup

LANGS = ("en", "fr")
HERE = Path(__file__).resolve().parent
FOLDER = HERE / "i18n"
# paths that are the same in every language: data files, static files, the 404 page
_SHARED = ("/data/", "/static/", "/favicon.ico", "/sitemap.xml", "/robots.txt", "/build.json", "/manifest")


def load(lang: str, *, prefix: str | None = None) -> dict[str, str]:
    """English -> lang from every fragment (optionally only fragments whose name starts with prefix)."""
    out: dict[str, str] = {}
    if lang == "en":
        return out
    for p in sorted((FOLDER / lang).glob("*.json")):
        if prefix and not p.stem.startswith(prefix):
            continue
        for k, v in json.loads(p.read_text(encoding="utf-8")).items():
            if not k.startswith("_") and v:
                out[k] = v
    return out


class Translated(str):
    """Text that has already been through _(): templates may pass it to _() again (a data label or a sentence
    built in Python), and it must come back as is, not be looked up or listed as missing."""


class Lang:
    def __init__(self, lang: str):
        self.lang = lang
        self.map = load(lang)
        self.missing: set[str] = set()

    def get(self, s: str) -> str:
        # already translated, or nothing to translate (an ISO date, a number, a code like "N/R")
        if self.lang == "en" or not s or isinstance(s, Translated) or not any(c.isalpha() for c in s):
            return s
        v = self.map.get(s)
        if v is None:
            self.missing.add(s)
            return s
        return v

    def __call__(self, s: str, **kw) -> str:
        t = self.get(s)
        return Translated(t.format(**kw) if kw else t)

    def html(self, s: str, **kw) -> Markup:
        t = Markup(self.get(s))
        return t.format(**kw) if kw else t

    def url(self, path: str) -> str:
        if self.lang == "en" or not path.startswith("/") or path.startswith("//") or path.startswith(_SHARED):
            return path
        return "/" + self.lang + path

    def other(self, path: str) -> str:
        """The same page in the other language (the toggle's link)."""
        if self.lang == "en":
            return "/fr" + path if not path.startswith(_SHARED) else path
        return path[len("/" + self.lang):] or "/" if path.startswith("/" + self.lang + "/") or path == "/" + self.lang else path


CURRENT = Lang("en")

NBSP = " "  # French groups thousands with a no-break space (as JavaScript's fr-CA does) and spaces "%" and "$"


def num(v, digits: int | None = None) -> str:
    """1234.5 -> "1,234.5" in English, "1 234,5" in French. Without digits, a number keeps the decimals it has
    (1.6 -> "1,6", 1.25 -> "1,25", 2.0 -> "2"); with digits, it is rounded to that many."""
    if v is None or v == "":
        return ""
    if isinstance(v, str):
        return v
    if digits is not None:
        s = f"{v:,.{digits}f}"
    elif isinstance(v, int) or v == int(v):
        s = f"{int(v):,}"
    else:
        s = f"{v:,.4f}".rstrip("0").rstrip(".")
    return s.replace(",", NBSP).replace(".", ",") if CURRENT.lang == "fr" else s


def pct(v) -> str:
    """A share: "45%" / "45 %"; "4.5" -> "4,5 %" in French. EQAO's text values ("<1") pass through."""
    if v is None or v == "":
        return ""
    s = v if isinstance(v, str) else f"{v:g}"
    return s.replace(".", ",") + NBSP + "%" if CURRENT.lang == "fr" else s + "%"


def money(v) -> str:
    """Whole dollars: "$1,234" / "1 234 $"."""
    if v is None or v == "":
        return ""
    n = num(round(v)) if not isinstance(v, str) else v
    return n + NBSP + "$" if CURRENT.lang == "fr" else "$" + n


def use(lang: str) -> Lang:
    """Switch the current language (the generator renders every page once per language)."""
    global CURRENT
    CURRENT = Lang(lang) if lang != CURRENT.lang else CURRENT
    return CURRENT


def _(s: str, **kw) -> str:
    return CURRENT(s, **kw)


def _h(s: str, **kw) -> Markup:
    return CURRENT.html(s, **kw)


def u(path: str) -> str:
    return CURRENT.url(path)


def js_module(lang: str) -> str:
    """The dictionary the browser scripts use: fragments named js-*.json plus data.json (labels that arrive in
    data files: data*.json), as an ES module the scripts import only on pages in that language."""
    d = load(lang, prefix="js-") | {k: v for k, v in load(lang).items() if k in load(lang, prefix="data")}
    return "// Generated by site/generate.py from site/i18n/" + lang + "/js-*.json and data.json. Don't edit.\nexport default " + json.dumps(d, ensure_ascii=False, sort_keys=True) + ";\n"
