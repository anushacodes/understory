# Understory — UI reference and implementation mapping

Updated: November 11, 2026. Status: implemented meadow direction with light/dark themes; desktop/mobile browser evidence is recorded in [VERIFICATION.md](VERIFICATION.md).

## Authority

The user identified [Understory.html](../Understory.html) as the reference for what the UI should look like. Preserve its visual identity and screen composition when implementing. It is an active design reference, not a discarded concept. [MVP_SCOPE.md](MVP_SCOPE.md) governs product behavior; the HTML does not expand repository understanding into issue/PR research.

The HTML is a self-contained board collection with nested bundled templates, scripts, fonts and imagery. These notes come from inspecting its embedded templates and styles, not a rendered-browser comparison. Keep the original file intact. Its packaging runtime and custom template syntax are reference infrastructure, not application architecture or a dependency requirement.

## Supplied boards

| Board | Preview size | Planning use |
| --- | --- | --- |
| Landing page · light | 1440 × 960 | Main landing composition, typography, meadow imagery and light palette |
| Product dashboard · light | 1440 × 900 | Three-pane repository/question/evidence workspace |
| Logo | 1280 × 900 | Lowercase wordmark, italic “under”, app monogram and named brand palette |
| Landing page · dark | 1440 × 960 | Dark landing treatment, warm accent and ambient effects |
| Product dashboard · dark | 1440 × 900 | Dark workspace palette and corresponding component treatment |
| Landing page · canyon option | 1440 × 960 | Alternate landing imagery/palette; selection remains open |

These sizes describe reference boards, not fixed browser dimensions. Both light and dark main designs are supplied references. The canyon board is explicitly an option; do not silently replace the main meadow direction with it or treat it as a third required shipped theme. Default theme, theme switching/persistence and final landing variant are unresolved choices.

## Visual identity

- **Wordmark:** lowercase `understory`, Instrument Serif, with `under` italicized. The logo board also supplies an italic `u` monogram on a rounded poppy tile.
- **Typography:** Instrument Serif for wordmark/display text; Inter for UI and body; JetBrains Mono for code, paths, SHAs and compact technical metadata. Preserve the roles and embedded references; verify font/asset distribution rights before shipping.
- **Landing:** scenic full-bleed imagery, layered washes for text legibility, centered oversized serif headline, italic accent line, compact supporting copy, a wide search/input container and rounded actions. The supplied headline is “Understand the code / beneath the surface.”
- **Workspace:** compact typography, neutral surfaces, fine dividers, restrained rounding, a dense file tree, readable code and small citation markers. Scenic landing imagery does not become a background behind workspace code.
- **Evidence:** numbered accent citation pills correspond to code gutter markers. Selected/cited lines use a warm highlight and a marigold edge; numbers and labels supplement color.

Observed landing measurements include a 1280px maximum header width, 24px horizontal padding, a 640px maximum input width and a 560px maximum supporting-copy width. The display size uses `clamp(56px, 8.6vw, 124px)` with line-height `0.98`; supporting copy is 18px/26px. Workspace base text is 13px/18px; source is 13px/23px. These are extracted reference values, not evidence of mobile usability or contrast compliance.

## Observed palettes

The landing and dashboard use distinct surface tokens. Preserve those differences instead of flattening them into one global background.

| Role | Landing light | Landing dark | Dashboard light | Dashboard dark |
| --- | --- | --- | --- | --- |
| Background | `#FBFAF5` | `#0F1410` | `#F4F4F1` | `#0E110F` |
| Card/pane | `#FFFFFF` | `#1A221C` | `#FFFFFF` | `#151916` |
| Main text | `#14201A` | `#F5F3EC` | `#1A1D1A` | `#EDEEEA` |
| Muted text | `#3E4A42` | `#DAD8CF` | `#5C615B` | `#AEB4AC` |
| Accent | `#D7352B` | `#F5C33A` | `#D7352B` | `#F47A6B` |
| Divider | `#14201A26` | `#F5F3EC40` | `#E5E5E0` | `#29302A` |
| Code highlight | Not applicable | Not applicable | `#FFF4CC` | `#3A3218` |
| Highlight edge | Not applicable | Not applicable | `#F5B700` | `#F5C33A` |

The logo board names Ink `#14201A`, Cloud `#FBFAF5`, Poppy `#D7352B`, Marigold `#F5B700`, Meadow `#3E7B2F`, Lilac `#A79BE0`, Turquoise `#45B5B8`, and Night `#0F1410`. Dashboard status/source treatments use softer companion fills. Canyon uses its own warm sand/brown/rose treatment; keep it isolated as an alternate until selected.

## Screen mapping

### Landing

Preserve the wordmark/header action, centered headline, scenic treatment, repository/question input and compact commit/citation promise. “Open Understory” opens the workspace. Repository input maps to authenticated registration/import for the owner; conceptual questions require an already selected ready repository. Define that routing explicitly rather than implying global search across unimported repositories.

The supplied supporting sentence contains an open-issue claim. Adjust that functional copy to the confirmed scope while preserving its placement and typography. Proposed replacement: “Search a repository by meaning, ask questions answered with cited code, and understand how the pieces fit together.” This copy is a planning proposal, not an edit to the reference file.

### Dashboard

| Region | Observed composition | Repository-understanding behavior |
| --- | --- | --- |
| Left | Wordmark, collapse control, repository/ref card, sidebar tabs, file filter/tree, indexed summary, new-question/history actions | Select repository/snapshot, explore inventory and exclusions, start a question, reopen retained runs |
| Middle | Question title, retrieval/read activity list, answer with citation numbers, bottom composer | Persisted job stages and inspected-source activity, validated answer/gaps, independent question submission |
| Right | File title and path/SHA metadata, toolbar, view/line controls, code with gutter numbers/citations, legend and open-file tabs | Stored source viewing at the answer's baseline, citation highlighting, copy path, commit-pinned GitHub link, cited/all range navigation |

The desktop reference uses a left pane with a 232px flex basis capped at 280px, a middle pane with a 340px basis capped at 400px, and a remaining evidence pane with a 560px basis. Primary toolbars are 56px high. Preserve the relative emphasis: source gets the largest area, and the question and its evidence remain visible together at the reference desktop width.

Overview and search results should use this shell rather than replacing it with an unrelated dashboard. Import/job/coverage controls should use the existing compact panel vocabulary. Source and answer selections must carry the same snapshot ID through every pane.

## Reconcile mock content with product contracts

| Reference detail | Planning resolution |
| --- | --- |
| Issues sidebar tab and issue-discussion activity/copy | Omit from the repository-only product; preserve the sidebar's visual treatment for supported content |
| “Ask a follow-up” composer | Keep composer placement/styling; label independent questions accurately until conversation memory is explicitly added |
| History | Reopen persisted question/overview runs; does not imply chat memory or a new multi-conversation data model |
| “Traced callers” / Callers tab | No complete call graph is promised. Omit unsupported controls/activity; only show static candidate references if a later measured feature implements them |
| “Checked tests” / Tests tab | Static source inspection or source filtering only; never executed tests, pass/fail or executed coverage |
| Hit counts, read-file activity and “hybrid retrieval” label | Render real retrieval/read metadata and effective mode; do not hard-code mock progress or hidden reasoning |
| Example repo, short SHA, code and confident answer | Synthetic illustration. Display real indexed data; use full SHA for source identity/links and qualify unsupported runtime claims |
| Cited/All control | Bounded source navigation; “All” does not bypass response-size limits |
| Split/expand controls and file tabs | Preserve useful evidence navigation; any rendered control must work, and absent behavior should not ship as a decorative button |
| Full-screen board sizes | Responsive layouts must preserve access to all panes and citation targets; board dimensions are not a mobile specification |

## States and verification

Preserve the supplied look across ready, loading, queued-worker-offline, retry, failed, empty, partial-coverage, no-results, model-unavailable and insufficient-evidence states. The reference primarily illustrates a populated workspace; missing states must extend that identity.

The landing contains slow background drift/breathing and dark firefly effects; the dashboard has a progress spinner. Reduced-motion rules are present in the reference and must remain effective. Keyboard focus, input labels, contrast, theme behavior and narrow-screen pane navigation need implementation verification; do not copy `outline: 0` without a visible focus replacement.

Before frontend work, record the selected landing variant and initial theme behavior. Compare implementation with the selected reference boards at their supplied desktop sizes and with the chosen responsive behavior at narrow widths. See UI-05/06 in [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md). No visual-fidelity check has passed during this documentation task.
