# Brief: make a template or script translatable, and translate it into French

Ontario School Finder (static site, Python + Jinja generator, vanilla JS modules) now builds every page twice: English
at `/…` and French at `/fr/…`. The owner asked for a French version "as best as you can, because it's better than
nothing": a careful machine translation, labelled on every French page as unreviewed (English is the reference).

Read first: `site/i18n.py` (how translation works), `site/templates/base.html` (a finished example), and the
glossary `site/i18n/glossary-fr.md` (use its terms every time).

## Converting a template (`site/templates/*.html`)

- Every visible English string and every English attribute (`aria-label`, `title`, `placeholder`, `alt`,
  `content`) becomes `{{ _("English text") }}`. Keep the English text exactly as it was (same words, same
  punctuation) so English pages don't change.
- Variables go in named placeholders: `{{ _("Schools in postal area {fsa}", fsa=f.fsa) }}`. Never build a sentence
  from translated fragments; translate whole sentences.
- A sentence with markup inside (a link, `<strong>`) uses `_h`: `{{ _h("Read <a href=\"{url}\">how it works</a>.",
  url=u("/methodology/")) }}`. Arguments are escaped automatically; only put markup in the string itself.
- Labels that come from data (`{{ q.label }}`, `{{ f.definition }}`, `{{ r.kind }}`-style lookups, Jinja dicts of
  English labels) become `{{ _(q.label) }}` so the data catalogue can translate them; list each such call site in
  your report.
- Every site link `href="/…"` becomes `href="{{ u('/…') }}"` (`u()` adds `/fr` on French pages). Leave `/data/…` and
  `/static/…` and external links alone. In Jinja, `u('/school/' ~ s.bsid ~ '/')`.
- Don't translate: school, board, city and document names; `{{ variables }}`; URLs; codes like `SP`, `N/R`.

## Converting a script (`site/static/js/*.js`)

- `import { t, u, num } from "./lib.js";` then every user-visible string becomes `t("English text")` or
  `t("Showing {n} schools", { n: count })`. Template literals with `${...}` inside must become a `t()` call with
  named placeholders. Links built in JS (`href="/school/..."`) go through `u()`. Pass numbers shown to people
  through `num()` where it's easy (French: "1 234").
- Labels that arrive in data (JSON) get `t(label)` too; list them in your report.
- Plurals: translate both forms as separate strings (`t("1 school")` and `t("{n} schools", {n})`).

## The catalogue

Write your French into one fragment per source file: `site/i18n/fr/<name>.json` (templates: the template's name,
e.g. `school.json`; scripts: `js-<name>.json`, e.g. `js-compare.json`). Keys are the exact English strings as written
in the code (after Jinja/JS unescaping), values the French:

```json
{ "_about": "Fragment for site/templates/school.html. Machine translation, unreviewed.",
  "Attendance and registration": "Fréquentation et inscription",
  "Schools in postal area {fsa}": "Écoles de la région postale {fsa}" }
```

Keep every `{placeholder}` and every HTML tag exactly. Canadian French, "vous", plain and short. Typography: French
quotes « … », a space before : ; ? ! and % (use a normal space), 3e année, 1 234.

## Check your work

- `node scripts/i18n-coverage.mjs <your file>`: must report 0 missing for your files.
- Templates: `.venv/Scripts/python.exe -c "from jinja2 import Environment, FileSystemLoader; Environment(loader=FileSystemLoader('site/templates')).get_template('<name>.html')"` must not error.
- Scripts: `node --check site/static/js/<file>.js`.
- Don't run `site/generate.py` or the pipeline (another person is building); don't edit files other than yours,
  except adding your fragment. On Windows never pipe a script into `python -`.

Report back in under 10 lines: strings converted, data-label call sites, anything you couldn't convert cleanly.
