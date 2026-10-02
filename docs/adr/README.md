# Architecture decision records

Each record follows Michael Nygard's form: context, decision, consequences. A record is never
edited to change its decision; a later record supersedes it and says so.

Most of the decisions below come from the Consensus deliberation `personal/logo-vectoriser`. That
was session `s-ce513c776105` on 2 October 2026, with Gemini, Grok and Opus taking part; Codex's
turn is still pending. The owner decided the open points the same day.

| ADR                                             | Title                                                       | Status   |
| ----------------------------------------------- | ----------------------------------------------------------- | -------- |
| [0001](0001-record-architecture-decisions.md)   | Record architecture decisions                               | Accepted |
| [0002](0002-stacked-potrace-is-the-baseline.md) | Stacked potrace is the baseline and the fallback            | Accepted |
| [0003](0003-analytic-geometry-only.md)          | Geometry is analytic; learned parts never touch coordinates | Accepted |
| [0004](0004-fitting-criterion.md)               | Fit by σ-normalised BIC on sub-pixel contours               | Accepted |
| [0005](0005-no-upsampled-tracing.md)            | No upsampled tracing; multi-scale is a confidence signal    | Accepted |
| [0006](0006-two-level-non-regression.md)        | Two-level non-regression, no percentage quotas              | Accepted |
| [0007](0007-measurement-conventions.md)         | Pinned renderer, noise floor and complexity conventions     | Accepted |
| [0008](0008-synthetic-first-corpus.md)          | Synthetic-first evaluation and a fail-closed corpus         | Accepted |
| [0009](0009-milestone-one-scope.md)             | Milestone 1 covers flat-colour marks only                   | Accepted |
| [0010](0010-public-standalone-repository.md)    | A public, standalone repository consumed by commit          | Accepted |
