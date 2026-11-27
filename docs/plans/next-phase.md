# Next phase (2026-11-26 late): everything left that can be built, plus a French version

Owner asked: "Start on all [the options] ... fully flesh it out, and also do the French version as best as you
can, because it's better than nothing, and add an easy accessible toggle for it" (look at union-communications for
how UnionOps did it: next-intl, /en /fr prefixes, messages/{en,fr}.json, LanguageToggle EN/FR buttons with lang,
aria-current, 44px).

Constraints: deploy at most once an hour; the 23:06 deploy of #27 FAILED ("Cannot deploy"; server nearly out of
disk, ~22 images of ~1.1 GB). A retry was refused by the safety classifier: no more deploys until the owner frees
space. site/dist is 1.1 GB (school pages 633 MB, data 382 MB); static /fr/ pages add ~670 MB per image.

## Items (branch feat/next-phase unless noted)
1. School website link sweep: all 4,945 Ministry school links; dead / parked / redirected to an unrelated domain ->
   hide the link and say why (never guess a replacement); refuses-automated-check -> keep. Report list.
2. Pipeline writes site/data atomically (build into a temp folder, swap at the end) so a crash leaves the old data.
3. Compare-from-search e2e test: wait for search results instead of racing (flaky against production).
4. Board pages: EQAO questionnaire for the whole board (board vs Ontario), same rules as school pages.
5. Capacity: transcribe per-school OTG capacity + enrolment for the largest boards that publish a table
   (docs/capacity-sources.md), as school records (kind projection), researcher + verifier, by hand.
6. French: /fr/ static pages from the same templates; catalogue site/i18n/fr.json (English source string -> French);
   JS t() with the same catalogue; board records get summary_fr; machine translation labelled as unreviewed, English
   is the reference; header EN/FR toggle to the same page; hreflang; sitemap; tests for catalogue coverage.

## Status
- [ ] 2, 3 (small)  - [ ] 1  - [ ] 4  - [ ] 5  - [ ] 6  - [ ] check.sh, PR(s), owner frees disk, deploy
