# Contributing

Thanks for helping keep Ontario School Finder accurate.

## Data corrections (most welcome)

Every number on the site comes from a public source and links to it. If something is wrong, it is
usually wrong at the source, or the site matched it to the wrong school. Tell us:

- on the site: **Report a correction** on any school page, or the [Corrections page](https://ontarioschoolfinder.ca/corrections/);
- or here: open a **Data correction** issue.

Please include the school (its page link or school number), what's wrong, and where the right
value is published. We fix matching errors in the pipeline; errors in the source data are reported
to the publisher and noted on the site.

## Bugs and ideas

Open a **Site bug** issue with the page, your device and browser, and what you expected. For ideas,
open an issue first so we can talk about it.

## Code

The code is public so anyone can check how the site works, but it is not released under an
open-source licence (see "Copyright and reuse" in the [README](README.md)). Please **open an issue
before sending a pull request**. Unrequested pull requests may be closed.

If you are working on it:

- Read [docs/HANDOFF.md](docs/HANDOFF.md) (lessons and traps) and [docs/DECISIONS.md](docs/DECISIONS.md) first.
- `./check.sh` is the definition of done: a clean rebuild from the original sources plus every test.
- Never commit downloaded data, generated data, `.env` files or addresses: `pipeline/cache/`,
  `site/data/` and `site/dist/` are ignored on purpose, and `CONTACT_EMAIL` comes from your environment.
- Plain language on every page, every number linked to its source, and missing values labelled, never shown as 0.
