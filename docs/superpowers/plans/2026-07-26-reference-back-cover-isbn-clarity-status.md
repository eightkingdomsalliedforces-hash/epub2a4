# Reference Back Cover and ISBN Clarity Status

Implementation completed on branch `fix/reference-back-cover-isbn-clarity`.

- Reference back-cover geometry implemented from safe-area ratios.
- Publisher logo slot uses `contain` and does not generate or bundle an image.
- Candidate cards show one recommended ISBN-13.
- A corresponding ISBN-10 appears only when it converts to that same ISBN-13.
- Unexplained resolved ISBN lists were removed from the search summary.
- Regression tests were written before production changes; the geometry test failed against the previous 55% layout as expected.

Full platform verification is pending for the current user-authored head.
