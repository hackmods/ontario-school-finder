# Security

Ontario School Finder is a static website: there are no accounts, no database, no forms that store
anything, and no cookies. Searches by address go from your browser straight to the Government of
Canada's geolocation service; "Use my location" never leaves your device.

## Reporting a problem

Please report security problems **privately**, not in a public issue:

- Use GitHub's **Report a vulnerability** button on this repository's **Security** tab, or
- write to the contact address on the site's [Corrections page](https://ontarioschoolfinder.ca/corrections/).

Include the page or file, what you found, and how to reproduce it. You'll get a reply within a few
days. Please give us a reasonable time to fix it before telling anyone else.

## In scope

- The site at https://ontarioschoolfinder.ca and the code in this repository: the page generator,
  scripts, nginx configuration (`deploy/`), and the data pipeline.
- Things like script injection through source data, a weakened Content-Security-Policy, or a
  third-party request the site says it doesn't make.

Out of scope: wrong or outdated *data* (use a [data correction](../../issues/new/choose) instead),
and the services the site links to or loads map tiles from.
