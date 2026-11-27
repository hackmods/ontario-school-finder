# Brief: translate board records into French

Every school page shows its board's hand-checked records (registration, French programs, transfers, buses, special
education, plans...). The French pages need a French summary for each record. This is a machine translation,
labelled on every French page as unreviewed; the English record stays the reference.

Read first: the glossary `site/i18n/glossary-fr.md` (use its terms every time) and the rules in
`docs/board-info.md` (what the records are). Canadian French, "vous", plain and short; French typography (« … »,
a space before : ; ? ! and %, 3e année, 1 234).

For each board number you're given, read `site/board-info/<board>.json` and write
`site/board-info/fr/<board>.json`:

```json
{ "_about": "French summaries for site/board-info/<board>.json. Machine translation, unreviewed.",
  "<record id>": { "summary": "<French summary>" } }
```

Translate the `summary` of every record in `records`, every `decisions` entry and every school record in `schools`
**except** ids containing `-capacity-` (those are generated separately). Keep exactly: numbers, dates, grades,
school/board/city/consortium names, document titles in quotes, phone numbers, emails, URLs. Say the same thing,
no more and no less: don't add advice, don't drop conditions ("as space allows", "case by case"), and keep "we
couldn't check/read" wording as an honest « nous n'avons pas pu vérifier ». For French-language boards' records,
which describe French pages in English, translate back into natural French.

Keep each French summary under 700 characters. Don't edit the English files. Validate each JSON file parses and
has one entry per translated id: `node -e "const e=require('./site/board-info/B66150.json'),f=require('./site/board-info/fr/B66150.json');const ids=[...e.records,...(e.decisions||[]),...Object.values(e.schools||{}).flatMap(s=>s.records)].map(r=>r.id).filter(i=>!i.includes('-capacity-'));console.log(ids.filter(i=>!f[i]))"`
(must print an empty list). On Windows never pipe a script into `python -`.

Report in under 5 lines: boards done, records translated, anything unclear.
