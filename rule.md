Typography
Font: Inter (primary) — system-ui fallback
Scale:
  Page title      — 20px / semibold / tracking-tight
  Section heading — 14px / semibold / uppercase / tracking-wider / muted
  Body            — 14px / regular
  Label           — 13px / medium
  Caption / meta  — 12px / regular / muted
  Code / ID       — 12px / mono

Color System
Line height: 1.5 body, 1.2 headings
Never use bold inside table cells — use weight contrast (medium vs regular) instead

Base (light mode default, dark mode respected via CSS vars)

  Background      — zinc-50   (page canvas)
  Surface         — white     (cards, drawers, sidebar)
  Border          — zinc-200  (all dividers, outlines)
  Border subtle   — zinc-100  (inner separators)
  Text primary    — zinc-900
  Text muted      — zinc-500
  Text disabled   — zinc-400

Accent (single, not rainbow)
  Brand           — primary (slate-900 or configured token)
  Brand subtle    — slate-50 (tinted backgrounds)

Semantic (status only — never decorative)
  Verified / Success   — emerald-600  bg: emerald-50
  In Progress          — blue-600     bg: blue-50
  Under Review         — amber-600    bg: amber-50
  On Hold              — zinc-500     bg: zinc-100
  Dismissed            — red-600      bg: red-50
  Resolved             — emerald-600  bg: emerald-50
  AI Flag              — orange-600   bg: orange-50

Rule: semantic colors appear only in status pills and alert banners.
      Never use color to decorate charts, headings, or empty states.

Border Radius
Sharp by default. No bubbly UI.

  radius-sm   — 4px   → inputs, table cells, inline badges
  radius-md   — 6px   → cards, drawers, dropdowns, modals
  radius-lg   — 8px   → sidebar, sheet overlays
  radius-full — 9999px → status pills ONLY

Buttons       → 6px (radius-md), never pill-shaped
Avatars       → 6px (rounded square), never circle
Modals        → 8px
Inputs        → 6px

Never use rounded-xl, rounded-2xl, rounded-3xl anywhere.

Spacing
Base unit: 4px

Page padding        — 24px (px-6)
Section gap         — 24px
Card inner padding  — 16px (p-4)
Table cell padding  — 10px 12px
Filter bar gap      — 8px between chips/controls
Sidebar padding     — 12px 16px per item
KPI card gap        — 16px
Form field gap      — 16px vertical

Sidebar width       — 224px expanded / 52px collapsed
Drawer width        — 440px (right-anchored)
Content max-width   — 1200px centered on wide viewports

Sidebar
Structure:
  ┌────────────────────────┐
  │  [mark] CitiSense      │  ← 16px semibold, logo left-aligned
  │  ───────────────────── │  ← separator: border-b zinc-100
  │  [sq avatar] Name      │  ← 13px medium, role badge right
  │  Office / Barangay     │  ← 12px muted below name
  │  ───────────────────── │
  │                        │
  │  NAVIGATION            │  ← 11px uppercase tracking-widest muted
  │  [icon] Dashboard      │
  │  [icon] Feedback    3  │  ← count: 12px mono muted, right-aligned
  │  [icon] Reports        │
  │  [icon] Accounts       │
  │  [icon] Activity Logs  │
  │  [icon] Settings       │
  │                        │
  │  ───────────────────── │
  │  [icon] Logout         │  ← bottom-pinned, text-red-500 on hover only
  └────────────────────────┘

Active state:
  — bg-zinc-100, text-zinc-900, icon filled
  — NO left accent bar (too decorative)
  — NO bold text on active (weight already communicates it)

Hover state:
  — bg-zinc-50, transition 100ms

Collapsed (icon-only):
  — 52px wide, tooltips on hover, same active logic
  — Logo collapses to mark only
  — Avatar removed, user section hidden

Section label "NAVIGATION" hides when collapsed.
No nested sub-nav items. No accordions in sidebar.

Buttons
Hierarchy — use sparingly, max 2 per context:

  Primary    — bg-zinc-900 text-white hover:bg-zinc-800
  Secondary  — border border-zinc-300 bg-white hover:bg-zinc-50
  Ghost      — no border no bg hover:bg-zinc-100
  Destructive— border border-red-200 text-red-600 hover:bg-red-50
  Link       — text-zinc-600 underline-offset-4 hover:underline

Sizes:
  Default    — h-9 px-4 text-14 font-medium
  Small      — h-7 px-3 text-13
  Icon       — h-8 w-8 (ghost by default)

Rules:
  — One primary button max per page section
  — Never two primary buttons side by side
  — Destructive actions get secondary or destructive style, never primary
  — No icon + label in primary unless the icon adds critical meaning
  — Loading state: spinner replaces label text, width locked

Inputs and filter
Input field:
  h-9 / border border-zinc-300 / bg-white / radius-md
  focus: ring-1 ring-zinc-900 border-zinc-900
  placeholder: text-zinc-400
  label: 13px medium, above field, gap-1.5

Search input:
  Prepended search icon (zinc-400), clearable (× appears when filled)
  Never a button attached to it

Filter bar pattern:
  Horizontal row, gap-2, wraps on narrow
  Filters = Select triggers (not checkbox dropdowns)
    → h-8 compact selects, border-zinc-200, chevron icon right
  Active filter shows value inline: "Status: Verified ×"
  "Clear all" — ghost, text-zinc-500, appears only when ≥1 filter active
  Toggle (e.g. "Flagged only") — small Switch, label left, right-aligned in bar

Never use full-width filter sections.
Never stack filters vertically.

Tables
Structure:
  — No outer card wrapper. Table sits on page surface with border-b only.
  — thead: bg-zinc-50, border-b border-zinc-200
  — th: 12px uppercase tracking-wider text-zinc-500 font-medium
  — td: 14px text-zinc-700, border-b border-zinc-100
  — tr hover: bg-zinc-50 transition 80ms
  — No striped rows. No colored rows.

Column rules:
  — First column: primary identifier, text-zinc-900 medium
  — Status columns: pill inline (do not center-align pills)
  — Actions column: right-aligned, icon buttons (ghost), visible on row hover only
  — Timestamps: 12px mono muted, never prominent
  — Never show more than 2 action buttons per row — overflow to [...] menu

Row actions [...] menu:
  — Popover, not dropdown select
  — Items: 14px, icon left, destructive items at bottom with separator + red text

Empty state:
  — Center-aligned in table body: icon (outline, zinc-300) + short message (zinc-500)
  — No illustration. No "No results found!" with exclamation.
  — If filterable: "No feedback matches these filters." + ghost "Clear filters" link

Status Pills
Shape: rounded-full, h-5, px-2.5, text-12 font-medium
No icon inside pill (icon-only for AI flag, not status)

Verification:
  Under Review  — bg-amber-50   text-amber-700
  Verified      — bg-emerald-50 text-emerald-700
  Dismissed     — bg-red-50     text-red-600

Resolution:
  —             — bg-zinc-100   text-zinc-500  (unset/none)
  In Progress   — bg-blue-50    text-blue-700
  On Hold       — bg-zinc-100   text-zinc-600
  Resolved      — bg-emerald-50 text-emerald-700

AI Flag badge:
  — Icon only: orange warning triangle, 14px, no pill
  — Tooltip on hover: flag reason
  — Never a full banner in table row — detail view only

Card and containers
Rule: a box exists only if it holds interactive or grouped content
      that cannot exist as a section on the page surface.

KPI cards:
  — border border-zinc-200, bg-white, radius-md, p-4
  — Label: 12px muted uppercase  Value: 24px semibold zinc-900
  — Trend: 12px arrow + delta, colored only if meaningful (green/red)
  — No icon decoration. No shadow.

Chart cards:
  — Same border/bg/radius as KPI
  — Header: 14px medium title left, ghost "Explain" button right
  — Chart fills remaining height
  — AI explanation: renders below chart inline, bg-zinc-50 border-t p-3,
    dismissed with × — not a popover, not a modal

Do NOT wrap tables in cards.
Do NOT wrap filter bars in cards.
Do NOT double-border: no card inside a card.
No box-shadow on any element except modals (shadow-md).Rule: a box exists only if it holds interactive or grouped content
      that cannot exist as a section on the page surface.

KPI cards:
  — border border-zinc-200, bg-white, radius-md, p-4
  — Label: 12px muted uppercase  Value: 24px semibold zinc-900
  — Trend: 12px arrow + delta, colored only if meaningful (green/red)
  — No icon decoration. No shadow.

Chart cards:
  — Same border/bg/radius as KPI
  — Header: 14px medium title left, ghost "Explain" button right
  — Chart fills remaining height
  — AI explanation: renders below chart inline, bg-zinc-50 border-t p-3,
    dismissed with × — not a popover, not a modal

Do NOT wrap tables in cards.
Do NOT wrap filter bars in cards.
Do NOT double-border: no card inside a card.
No box-shadow on any element except modals (shadow-md).

Drawers and modals
Drawer (right-anchored):
  — Width: 440px, full-height, border-l border-zinc-200
  — bg-white, no shadow on content (border is enough)
  — Header: 16px semibold title + × close icon-button, border-b
  — Content: scrollable, px-5 py-4 sections separated by border-b zinc-100
  — Footer (if actions): sticky bottom, border-t, bg-white, px-5 py-3, right-aligned

Modal (destructive confirm only):
  — Max-width 400px, centered, shadow-md, radius-md
  — Title: 15px semibold  Body: 14px muted
  — Confirm button: destructive style  Cancel: ghost
  — Never used for forms. Never used for status changes.

Inline confirm rail (for reversible actions — dismiss, suspend):
  — Appears below trigger button in same container, not floating
  — bg-zinc-50 border border-zinc-200 rounded-md px-3 py-2 mt-1
  — Small text field if reason required + Confirm (destructive) + Cancel (ghost)
  — Closes on cancel, on confirm fires action + shows toast

Toast and feedback
Position: bottom-right, stacked, max 3 visible

Toast anatomy:
  — bg-zinc-900 text-white, radius-md, px-4 py-3, shadow-lg
  — Icon left (check / × / warning — 16px) + message + optional action link
  — Auto-dismiss: 4s. Pause on hover.

Types:
  Success  — zinc-900 bg (don't use green bg for toast — too loud)
  Error    — red-700 bg
  Undo     — zinc-900 bg + "Undo" text-button right (5s timer)

Never use toast for form errors — those live inline under fields.
Never stack more than one error toast.

Page header pattern
Every page:
┌─────────────────────────────────────────────────────┐
│ [Page title]                    [Primary action CTA] │
│ [Subtitle — only if non-obvious, 13px muted]         │
└─────────────────────────────────────────────────────┘

Rule: subtitle is optional. If title is self-explanatory, omit it.
No breadcrumbs unless 3+ levels deep (only Account Detail qualifies).
No icon next to page title.
The page header is NOT inside a card or a bordered container.

What to eliminate
✗  rounded-xl / 2xl / 3xl anywhere
✗  gradient backgrounds (headers, cards, banners)
✗  icon + label in every table row (icon-only actions, labeled in tooltip)
✗  section titles that restate the page title ("Feedback List" under "Feedback")
✗  empty state illustrations (SVG drawings)
✗  card wrapping a table
✗  card wrapping a filter bar
✗  double borders (card border + inner table border)
✗  placeholder text that says "Search feedbacks..." — just "Search"
✗  confirmation modals for status toggle changes
✗  color-coded sidebar nav items
✗  full-page loading spinners — skeleton rows only
✗  "No data available" — write actual context-aware empty messages
✗  avatar circles — use rounded squares
✗  primary buttons for every action — 80% of actions should be ghost or secondary
✗  "Are you sure?" modals for non-destructive actions
✗  showing all status options always — show current + available transitions only