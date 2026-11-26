# Ontario School Finder branding

**Launch design: Field Guide.** The current selection lives in [brand.json](brand.json). The three original 1960s–70s-inspired trillium designs are preserved in [the gallery](trillium-retro/gallery.html) and [its PNG preview](trillium-retro/gallery.png).

| Design | Character | Source assets |
| --- | --- | --- |
| Civic Trillium | Faceted petals, forest green, Franklin Gothic Heavy | [Folder](trillium-retro/civic-trillium/) |
| Common Bloom | Rounded petals, harvest colours, Cooper Black | [Folder](trillium-retro/common-bloom/) |
| Field Guide | Repeating petal contours, olive/orange/ochre, Rockwell | [Folder](trillium-retro/field-guide/) |

Each folder contains the original transparent `logo.svg`, `logo-mono.svg`, `logo-reversed.svg`, `mark.svg`, a presentation PNG, and a complete generated `web/` asset set. All SVG lettering is outlined: no font installation or external resource is needed to display the logos. The SVG masters remain editable vector artwork. These are original proposals, not reproductions of government logos.

## Switch the website to another design

From the repository root, with dependencies installed:

```sh
npm run brand -- --brand civic-trillium
# or: npm run brand -- --brand common-bloom
# or: npm run brand -- --brand field-guide

.venv/Scripts/python site/generate.py  # .venv/bin/python on macOS/Linux
```

The command renders the selected design, saves its full web set, copies it to `site/static/img/`, and records the selection in [brand.json](brand.json). It updates the header/footer artwork, SVG favicon, Apple/PWA PNG icons, maskable icon, and social-share card together. Build with the owner's existing `CONTACT_EMAIL` environment setting, verify, commit both `branding/` and the changed runtime assets, then follow the repository publishing workflow.

To regenerate all saved web sets while keeping Field Guide active:

```sh
npm run brand -- --all --brand field-guide
```

Artwork changes belong in the original SVG masters. The rendering script uses the selected palette from `brand.json`. It creates a tighter web lockup and a two-contour Field Guide favicon for small sizes; the original three-contour design is retained in large icons and logos. The maskable icon keeps the symbol within its central safe circle.

## Website use

The header/footer use the full wordmark with an accessible home-link label. A separate white version appears in dark mode; print uses the colour version. The website's existing body typography, data colours and controls remain independent of the logo choice. `site/static/css/brand.css` owns the logo sizing, so swapping a logo does not require editing shared application styles.

The three palettes and individual previews are retained for future decisions. The archive is not copied into the public website: only the selected runtime assets are published.

Ontario reference: [the trillium is Ontario's floral emblem](https://www.canada.ca/en/canadian-heritage/services/provincial-territorial-symbols-canada/ontario.html).
