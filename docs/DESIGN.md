# BlunderTrace — Design Language: "The Annotated Book"

The visual and interaction spec for the frontend. **The goal is pixel-perfect fidelity to the
approved design.** When this document and the reference files disagree, the reference files win;
fix this document.

- **Approved design (interactive canvas, private):** claude.ai artifact "BlunderTrace Design
  Directions", column A.
- **Reference files of record (in this repo):** `docs/design/reference/` — `home.dc.html`,
  `analysing.dc.html`, `report.dc.html`, `game.dc.html`. Every value below was taken from them.
  (They render inside the canvas runtime; read them for exact styles. Their internal links still
  use the canvas names `Main` / `AAnalysing` / `AReport` / `AGame`.)

---

## 1. Concept
The product reads like **a chess book written about the user**: calm pages, generous whitespace,
diagrams as book plates, chess annotation glyphs instead of badges, and sources as footnotes.
The brand motif is **the trace** — a game's evaluation line, flat until the blunder, then plunging.

**Principles (anti-bloat rules):**
1. One primary thing per screen.
2. Detail only on request (collapsed chapters, hover footnotes, side panel).
3. A number is shown only if the user can act on it.
4. Colour is reserved for errors and one accent; everything else is ink and bone.
5. Only notable moves carry a glyph; ordinary moves stay unmarked.
6. Whitespace is a feature — it leaves room to grow (e.g. the post-launch coach chat).

---

## 2. Colour tokens
One dark theme only (no theme switching). Token names are the Tailwind names used in code
(`frontend/src/styles/tokens.css`): `bg-page`, `text-bone`, `muted`, `border-rule`, …

| Token | Hex | Used for |
|---|---|---|
| `page` | `#12110F` | Page background (warm ink) |
| `surface` | `#1B1A17` | Board plates, move-list panel, footnote preview, table-row hover |
| `surface-hover` | `#23211D` | Hover on move buttons and controls |
| `selected` | `#2E2B25` | Current move in the move list; faint trace and midline in the home hero |
| `rule` | `#34312B` | Main borders and section rules |
| `rule-strong` | `#4A463E` | Input underline, secondary-button border, avatar ring, footnote-preview border |
| `rule-subtle` | `#2A2823` | Footnote rule, table row borders, eval-bar track, opening-bar track |
| `rule-faint` | `#1F1E1A` | Contents rows (Analysing) |
| `leader` | `#3A372F` | Dotted leaders (Analysing) |
| `bone` | `#ECE7DD` | Primary text ("bone"); primary-button background |
| `muted` | `#A39D91` | Secondary text, labels, captions |
| `faint` | `#8A8478` | Roman numerals, move numbers, placeholders, row numbers |
| `on-bone` | `#12110F` | Text on bone (primary button) |
| `accent` | `#6FC2AE` | Brand accent ("verdigris"): wordmark *Trace*, links, focus ring, selected underline, better-line arrows, footnote markers, `!`/`!!` glyphs, current-trace stroke |
| `accent-hover` | `#9AD9CA` | Link hover |
| `blunder` | `#EF6B5E` | `??`, refutation arrows, lost results, low opening scores |
| `mistake` | `#E8954A` | `?` |
| `inaccuracy` | `#D9BE5C` | `?!` |

**Contrast (WCAG 2.1, on `page` unless stated):** bone 15.3:1 · muted 7.0:1 · faint 5.1:1 ·
accent 9.0:1 · blunder 6.2:1 · mistake 7.9:1 · inaccuracy 10.3:1 · on-bone on bone 15.3:1 ·
bone on `selected` 11.5:1. All text passes AA (4.5:1).

---

## 3. Typography
Three voices, like a chess book. Self-hosted via Fontsource (all SIL OFL 1.1).

| Role | Family | Weights / axes |
|---|---|---|
| **Display** | Fraunces (variable) | wght 300–600, opsz 9–144 (automatic optical sizing), italic |
| **UI** | Geist | 400, 500, 600 |
| **Notation** | Geist Mono | 400, 500 |
| **Pieces** | Noto Sans Symbols 2 | regular (chess glyphs only) |

**Type scale (exact values from the reference):**

| Style | Font | Size / line-height / tracking | Where |
|---|---|---|---|
| Hero title | Fraunces 400 | `clamp(44px, 6.4vw, 76px)` / 1.02 / −0.025em | Home h1 (second line italic, accent) |
| Page title | Fraunces 400 | `clamp(40px, 5vw, 60px)` / 1.05 / −0.02em | Report h1 (username); Analysing h1 uses `clamp(40px, 5vw, 58px)` |
| Game title | Fraunces 400 | 38px / normal / −0.01em | Game view h1 |
| Section | Fraunces 400 | 34px / −0.01em | Report "Three habits that cost you games" |
| Chapter title (open) | Fraunces 400 | 36px / 1.15 | Weakness card I |
| Chapter title (collapsed) | Fraunces | 30px / 1.15 | Weakness cards II, III |
| Roman numeral | Fraunces | 28px, `faint` | "I." "II." "III." |
| Subsection | Fraunces 400 | 26px | Tactics you missed, Openings, Your games |
| Panel grade | Fraunces | 30px | Side panel "Blunder" / "Great move" |
| Contents heading | Fraunces italic | 24px | Analysing "Contents" |
| Wordmark | Fraunces | 22px (20px in game header) / −0.01em | "Blunder" + italic "Trace" in accent |
| Key question | Fraunces italic | 19px | "after this, what can my opponent capture — and is it defended?" |
| Caption / note | Fraunces italic | 16–17px, `muted` | Figure captions, line notes, hints |
| Username input | Fraunces | 30px | Home input |
| Lead | Geist 400 | 18px / 1.6, `muted` | Home intro; Analysing 17px / 1.6 |
| Body | Geist 400 | 17px / 1.7 | Chapter text |
| UI | Geist 500–600 | 15px | Buttons, toggles, table, preview name |
| Small | Geist | 14px (links), 13px (footnotes, line-height 1.8) | |
| Label | Geist Mono | 12px, uppercase, +0.08em, `muted` | "WHY IT HAPPENS", "CHESS.COM USERNAME", eyebrows |
| Notation | Geist Mono | 13px / 1.55 (hero), 15px (move list), 17px / 1.6 (line text) | Moves |
| Data | Geist Mono | 15px; big count 30px; eval 14px; dates 13px | Counts, evals |

---

## 4. Layout & spacing
- **Page padding:** 28px top, 24px sides, 72–96px bottom.
- **Content widths:** Home and Game 1160px · Report 1080px · Analysing text column 760px.
- **Header:** wordmark left, one small item right (mono tagline, link or report id), baseline-aligned.
- **Corners:** 2px radius on buttons only; plates, panels and cards are square.
- **Borders:** always 1px.
- **Layout primitive:** flex rows that wrap (`flex-wrap: wrap`) with explicit gaps; desktop-first,
  columns stack on narrow screens (full phone review is a post-launch item).

| Screen | Key measurements |
|---|---|
| Home | main 72px below header; columns gap 64px (row) / 88px (column); text column `flex: 1 1 440px`; figure `flex: 0 1 460px`, board max 440px |
| Analysing | title block 64px below header; progress 36px below lead; "Contents" 56px below |
| Report | title block 64px below header; first section 72px below; chapters separated by a 1px `rule` with 28px top margin and 32px padding; chapter body gap 40px / 64px; example board 320px; footnotes 40px below text with a `rule-subtle` top border |
| Game | main 32px below title; columns gap 40px / 56px; board column `flex: 0 1 620px`; aside `flex: 1 1 320px`; eval bar 14px wide with 10px gap; trace 22px below controls; panel 20px below move list |

---

## 5. The board
Rendered with **chessground** (view-only), themed to match exactly.

| Property | Value |
|---|---|
| Light squares | `#D9CEB6` |
| Dark squares | `#7D8B95` |
| Last-move highlight | light `#CFD9B9`, dark `#7FA39A` (squares recoloured, not overlaid) |
| Coordinates (game view only) | Geist Mono, 1.9% of board width; rank top-left of a-file squares, file bottom-right of rank-1 squares; on light squares `#5E6B74`, on dark `#E4DBC6` |
| Plate | `surface` background, 1px `rule` border, padding 10px (home) / 8px (report, game) |
| Orientation | White at the bottom (the user's colour later if needed) |

**Pieces — exactly as designed:**
- Glyphs: ♚ ♛ ♜ ♝ ♞ ♟ (U+265A–U+265F) followed by U+FE0E (text presentation), the *solid* shapes
  for both colours, font **Noto Sans Symbols 2**.
- Size: 10.4% of board width (83% of a square), centred, line-height 1.
- White: fill `#F7F2E8`, outline 0.34% of board width in `#22201C` (the outline is what separates
  white pieces from light squares).
- Black: fill `#1D1C19`, no outline.
- Implementation: style chessground's piece elements with the glyph as content (font self-hosted),
  or export the glyphs to SVG once and use them as piece images — either way identical shapes.

**Arrows:**
- Shaft 1.5% of board width thick with rounded ends; head 3.4% long × 4.6% wide; opacity 0.85.
- Start 0.28 squares from the origin square's centre; tip 0.22 squares short of the target's centre.
- Colours: **better line = `accent`**, **refutation / threats = `blunder`**.
- chessground's arrows are configured (brush colour, width, opacity) to match these as closely as
  its arrow shape allows.

**Evaluation bar (game view):** 14px wide, track `rule-subtle` with a 1px `rule` border; the
`bone`-coloured fill grows from the bottom to **White's win %**; height transition 0.4s ease. The
numeric eval appears below the board in Geist Mono 14px: `+0.3`, `−1.5`, `−M` (true minus sign).

---

## 6. The trace
White's win % over the game (win % formula: `docs/PLAN.md` §4.2), plotted as a line:
`y = pad + (100 − win%) / 100 × (height − 2·pad)`; up = good for White.

| Instance | Size (viewBox) | Style |
|---|---|---|
| Home hero | 520 × 120, pad 6 | Dashed midline (`3 5`, `selected`, 1px); full path `selected` 2px; drawn part `bone` 2px, round joins/caps; blunder marker: ring r=7, `blunder` 2px + label "4. Nxe5??" in Geist Mono 13px `blunder` |
| Game view | 640 × 90, pad 6, stretched to the column | Dashed midline (`selected`); path `muted` 1.6px (non-scaling stroke); 8px dots in the grade colour at `??` `?` `?!` moves; current position = 14px ring, 2px `accent`, moves with 0.3s transition |
| Analysing rows | 120 × 24, pad 2 | Midline `rule-subtle`; path 1.5px `muted`, or `accent` while that game is being read |

---

## 7. Annotation glyphs (move grades)
Grades follow `docs/PLAN.md` §4.2. Shown as **chess annotation glyphs**, appended to the move
(e.g. `Nxe5??`), never as badges or icons.

| Grade | Glyph | Colour | Shown in move list? |
|---|---|---|---|
| Brilliant | `!!` | accent | yes |
| Great | `!` | accent | yes |
| Best / Excellent / Good | — | — | no (unmarked) |
| Inaccuracy | `?!` | inaccuracy | yes |
| Mistake | `?` | mistake | yes |
| Blunder | `??` | blunder | yes |
| Miss | (to be designed in phase 1, same glyph family) | — | yes |

Grade names in prose: "Blunder", "Mistake", "Inaccuracy", "Great move", "Brilliant".

---

## 8. Components
Built on **Reka UI** primitives (Radix for Vue) where behaviour is needed, styled only with the
tokens above.

| Component | Spec |
|---|---|
| **Primary button** | `bone` background, `on-bone` text, Geist 600 15px, min-height 48px, padding 0 28px, radius 2px. Smaller variant in panels: 14px, min-height 44px, padding 0 18px |
| **Secondary button** | transparent, 1px `rule-strong`, `bone`, Geist 500 14px, min-height 44px, padding 0 18px, radius 2px |
| **Icon control** (◀◀ ◀ ▶ ▶▶) | 48 × 44px, transparent, 1px `rule`, stroke icons 18px (1.8 stroke), hover `surface-hover`, disabled opacity 0.35, 4px gaps |
| **Username input** | underline only: 1px `rule-strong` bottom border, `accent` on focus; Fraunces 30px; padding 10px 0; placeholder `faint`; label above (Label style) |
| **Time-control toggle** (Reka ToggleGroup) | text buttons Geist 500 15px, min-height 44px, gap 24px; selected = `bone` + 1px `accent` underline; others `muted`; label shows counts once the player is known ("Rapid · 142") |
| **Player preview** | 40px circle, 1px `rule-strong`, initial in Fraunces 18px; name Geist 15px; Geist Mono 12px muted ratings line |
| **Chapter** (weakness card) | Numeral + Fraunces title + count ("9 of 20 games", number Geist Mono 30px); body = text column (Label + body paragraphs, key question in Fraunces italic) + figure (plate board, mono meta line, mono move line with glyph, Fraunces italic caption, links "Open in game view →" and "2 more examples") |
| **Collapsed chapter** (Reka Collapsible) | full-width button: numeral, 30px title, count, `+`/`−` in mono; expanded body indented 56px, max-width 640px |
| **Footnote marker** | superscript button, Geist 12px, `accent`, padding 0 3px |
| **Footnote preview** (Reka HoverCard/Popover) | 340px card, `surface`, 1px `rule-strong`, shadow `0 12px 32px rgba(0,0,0,0.45)`, padding 16px 18px; label "Retrieved passage · used for this advice" (Geist Mono 11px uppercase muted); the passage in Fraunces italic 16px; source in 13px muted. Opens on hover, focus or tap; closes on leave or blur |
| **Footnote list** | 13px / 1.8 muted, 1px `rule-subtle` top border, numbered links to sources |
| **Missed-tactics list** | rows with a 1px dotted `rule` bottom border; name + mono count |
| **Opening row** | name 16px + muted "· White · 7 games" 14px; 120 × 4px bar (track `rule-subtle`, fill `bone`, or `blunder` when score < 40%); score Geist Mono 15px right-aligned |
| **Games table** | header Geist Mono 12px uppercase +0.06em muted; rows bordered `rule-subtle`, hover `surface`; date mono 13px muted; opponent link in `bone` + muted "as White"; error glyph counts in grade colours, right-aligned, 12px apart; horizontal scroll below 640px |
| **Move list** | panel `surface` + 1px `rule`, padding 10px 8px, "Moves" label; rows `40px | 1fr | 1fr`; numbers mono 13px `faint`; move buttons min-height 36px, mono 15px, current = `selected` + weight 600, hover `surface-hover`; glyph appended in grade colour |
| **Side panel** | 1px `rule` top border, padding-top 22px, min-height 180px, `aria-live="polite"`. States: **error** (label "Your move" / "Your opponent's move", grade name Fraunces 30px in grade colour + move in mono 20px, "This lost N points of winning chance." 15px muted, buttons **Show better move** (primary) and **Show why it's bad** (secondary)); **line** (label "Better move" in accent or "Why it's bad" in blunder, the line in mono 17px, note in Fraunces italic 17px, button "↩ Back to game"); **great move** (accent); **hint** ("Step to a marked move — ?? ? ?! — to see what went wrong." Fraunces italic 17px muted) |
| **Progress rule** (Analysing) | 2px track `rule`, fill `bone`, width transition 0.3s; count "12 / 20" Geist Mono 14px |
| **Contents row** (Analysing) | min-height 46px, bottom border `rule-faint`; number mono 13px `faint` (34px column); "vs opponent" 15px + result in Fraunces italic (won `bone`, lost `blunder`, draw `muted`); dotted leader `leader`; 120 × 24 trace; right column 104px: "reading…" (muted) or error counts in grade colours or "clean"; queued rows at opacity 0.4 |
| **Focus ring** | 2px solid `accent`, offset 3px (2px in the game view) |

---

## 9. Screens
Exact layouts are in the reference files; this is the content order.

1. **Home** — header · hero title ("Every lost game has one moment." / *"Find yours."*) · lead ·
   username input · player preview (after typing) · time-control toggle · **Analyse my games** +
   "Last 20 games · about 3 min · no sign-up" · figure: animated board plate, trace, notation
   line, caption "Fig. 1 — …".
2. **Analysing** — eyebrow "Analysing" · *"Reading your games…"* (→ *"Your report is ready."*) ·
   lead incl. "You can close this tab — this page's link keeps working" · progress rule ·
   **Open your report →** (when finished) · "Contents": one row per game.
3. **Report** — eyebrow "Report" · username · summary line · "Three habits that cost you games":
   chapter I open, II and III collapsed · Tactics you missed + Openings (side by side, wrapping) ·
   Your games (table).
4. **Game view** — "← Back to report" · title "vs opponent" + mono meta line · board (eval bar,
   plate, coordinates, arrows) · controls + eval + "← → keys" hint · trace · move list · side panel.
   Opens at the move the user came from.

---

## 10. Motion
| What | Behaviour |
|---|---|
| Home hero | Plays the sample game one move per 1.1s up to the blunder sequence, holds ~4.4s, restarts; arrows appear on the double attack; trace draws in sync |
| Piece moves | chessground animation, **300ms** (calm); captures fade, castling moves both pieces |
| Line playback | first shows the arrow for the line's first move, then plays one move per 950ms; holds at the end; "↩ Back to game" restores the game position |
| Eval bar | height 0.4s ease |
| Trace marker | position 0.3s |
| Analysing | the current game's trace draws point by point; finished rows fill in; progress rule 0.3s |
| Footnote preview | appears instantly on hover/focus |
| **Reduced motion** (`prefers-reduced-motion`) | no autoplay (hero shows its final frame), no piece animation, no line autoplay steps beyond a static final position |

---

## 11. Interaction
- **Keyboard (game view):** ← / → step, Home / End jump to start / end, Esc leaves a line replay.
  Active while the board area has focus; the board area is focusable and announces the keys.
- **Clicks:** any move in the move list jumps there; examples on the report open the game view at
  that move; game-table rows open the game view.
- **Never:** dragging pieces, settings, theme switches, sign-in.

---

## 12. Voice & copy
- Plain English, second person ("you"), short sentences. Chess terms explained in passing.
- No exclamation marks in prose (chess glyphs only). No hype.
- Captions in book style: "Fig. 1 — …".
- True typographic characters: em dash —, ellipsis …, minus −, curly quotes “ ” ’.
- Moves always in SAN; move numbers "4." for White, "4…" for Black.
- Key strings (from the design): "Every lost game has one moment. *Find yours.*" ·
  "Analyse my games" · "Reading your games…" · "Your report is ready." · "Open your report →" ·
  "Three habits that cost you games" · "Why it happens" · "How to avoid it" ·
  "Show better move" · "Show why it's bad" · "↩ Back to game" ·
  "This lost N points of winning chance."

---

## 13. Accessibility
- All text ≥ 4.5:1 contrast (§2). Coordinates on dark squares (2.5:1) and white pieces on light
  squares (1.4:1 fill, separated by their dark outline) are decorative/graphical and labelled
  elsewhere.
- Real `<button>`, `<a>`, `<input>` + `<label>`; icon-only buttons have `aria-label`.
- Boards and traces carry `role="img"` + a text description; decorative SVGs are `aria-hidden`.
- Side panel is `aria-live="polite"`; toggles use `aria-pressed`; collapsibles use `aria-expanded`.
- Touch targets ≥ 44px except move-list buttons (36px; meets WCAG 2.2 AA 24px minimum).
- Visible focus ring everywhere (§8).

---

## 14. Implementation notes (phase 1)
- **Stack:** Vue 3 + Vite + TypeScript, Tailwind CSS v4 (tokens in `@theme`), Reka UI, Vue Router,
  VueUse, chess.js, chessground, Fontsource.
- **Tokens:** every value above becomes a token (colours, fonts, type scale, spacing, motion);
  components use tokens only — no raw hex in components.
- **Verification:** each screen is built against sample JSON (`docs/API.md`) and compared
  side by side with its reference file at 1440px width before it is considered done.
- Known unavoidable differences: chessground's arrow-head shape (colour, width and opacity match).
