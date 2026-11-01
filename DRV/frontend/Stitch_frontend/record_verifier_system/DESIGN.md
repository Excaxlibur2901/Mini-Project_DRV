---
name: Record Verifier System
colors:
  surface: '#101419'
  surface-dim: '#101419'
  surface-bright: '#36393f'
  surface-container-lowest: '#0a0f13'
  surface-container-low: '#181c21'
  surface-container: '#1c2025'
  surface-container-high: '#262a30'
  surface-container-highest: '#31353b'
  on-surface: '#e0e2ea'
  on-surface-variant: '#bec9c6'
  inverse-surface: '#e0e2ea'
  inverse-on-surface: '#2d3136'
  outline: '#889390'
  outline-variant: '#3f4947'
  surface-tint: '#87d4c9'
  primary: '#87d4c9'
  on-primary: '#003732'
  primary-container: '#5ca99e'
  on-primary-container: '#003b35'
  inverse-primary: '#0f6a61'
  secondary: '#97d1ca'
  on-secondary: '#003733'
  secondary-container: '#13524c'
  on-secondary-container: '#89c3bc'
  tertiary: '#b7cac8'
  on-tertiary: '#223332'
  tertiary-container: '#8da09e'
  on-tertiary-container: '#263736'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#a3f1e5'
  primary-fixed-dim: '#87d4c9'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#b3eee6'
  secondary-fixed-dim: '#97d1ca'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#0f4f4a'
  tertiary-fixed: '#d3e6e4'
  tertiary-fixed-dim: '#b7cac8'
  on-tertiary-fixed: '#0d1e1e'
  on-tertiary-fixed-variant: '#394a49'
  background: '#101419'
  on-background: '#e0e2ea'
  surface-variant: '#31353b'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 2.25rem
    fontWeight: '600'
    lineHeight: 2.75rem
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: 2rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 1.25rem
    fontWeight: '500'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 1rem
    fontWeight: '500'
    lineHeight: 1.5rem
    letterSpacing: 0em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
    letterSpacing: 0em
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.375rem
    letterSpacing: 0em
  body-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1.125rem
    letterSpacing: 0.01em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: 0.06em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.6875rem
    fontWeight: '500'
    lineHeight: 0.875rem
    letterSpacing: 0.08em
  code-data:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
    letterSpacing: -0.01em
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-xxs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style
The design system manifests an institutional, cryptographic ledger aesthetic. Designed specifically for archival validation, credential verification, and high-stakes evidentiary inspection, it prioritizes cold precision, unyielding stability, and zero-latency readability. 

The visual execution is strictly utilitarian and architectural. Drawing inspiration from command terminals and high-assurance forensic apparatus, the system rejects ornamental gradients, blur mechanics, or decorative softening. Interfaces convey unquestionable evidentiary certainty through exact alignment, rigid zero-radius boundaries, and high-density monospaced data structures.

## Colors
The palette is built upon a low-reflectance, deep slate ground layer, engineered to maintain eye comfort across prolonged cryptographic analysis sessions while maximizing data contrast.

### Core Canvas & Structure
- **Canvas Base:** `#14181D` provides a neutral deep slate foundation.
- **Surface Elevation 1 (Containers/Panels):** `#1B2227` provides crisp visual containment.
- **Surface Elevation 2 (Active/Raised Cells):** `#222B34` delineates sub-panels, headers, and interactive states.
- **Structural Outlines:** `#2E373F` provides an uncompromising 1px perimeter for all panels and inputs.

### Brand Accents
- **Primary Interactive (Accent):** `#5CA99E` provides deliberate focal contrast without luminescence.
- **Accent Hover:** `#86BBB4` provides immediate visual confirmation on pointer interaction.
- **Accent Muted/Subtle:** `#1E2F2E` acts as the backing layer for active navigational states and selected rows.

### Text Contrast Tiers
- **Display & Headings:** `#C9D3E0` ensures razor-sharp legibility across structural headers.
- **Primary Data & Text:** `#E7E4DC` delivers uncompromised optical legibility for forensic body data.
- **Muted Metadata & Structural Borders:** `#9AA4AD` manages non-essential labels, hash prefixes, and disabled indicators.

### Institutional Verification Tokens
Status indicators use balanced triple-token definitions (text, tinted background, and structural border):
- **Verified:** Text `#7CD5A7`, Background `#183325`, Border `#234E39`.
- **Mismatch:** Text `#F29E94`, Background `#3A1E1B`, Border `#5A2D28`.
- **Revoked:** Text `#E5BA6C`, Background `#362810`, Border `#533E1A`.
- **Not Found:** Text `#93C2EB`, Background `#192A3A`, Border `#264057`.
- **Needs Clarification:** Text `#C0C8D0`, Background `#222B34`, Border `#323E4B`.

## Typography
Typography is tuned for auditability, telemetry, and dense cryptographic records.

Headlines employ `Space Grotesk` to provide structured geometric balance, commanding authority across operational views without distracting from raw data.

All tabular rows, IDs, cryptographic proofs, hashes, inputs, and labels use `JetBrains Mono`. Monospaced tabular alignment ensures hash segments and checksum calculations align vertically down columns, eliminating character-width wobble during data streaming and side-by-side record diffing. All operational micro-labels use uppercase text with expanded tracking (`0.06em` to `0.08em`) for swift legibility at small sizes.

## Layout & Spacing
The layout model employs a rigid 12-column structural grid system with an aggressive spatial economy designed to maximize information density.

- **Desktop (1200px+):** 12-column fluid grid, 24px (`1.5rem`) outer canvas margins, and 16px (`1rem`) gutters. Side-by-side ledger comparisons lock to dual 6-column arrangements.
- **Tablet (768px - 1199px):** 8-column layout with 16px gutters and margins. Panes transition into vertically stacked inspection views.
- **Mobile (< 768px):** 4-column layout with 12px gutters and 16px margins. Monospaced tabular data cascades into horizontal scroll viewports with preserved column widths.

Padding within components adheres strictly to base-4 increments, maintaining rhythm without superfluous empty space.

## Elevation & Depth
Elevation is articulated exclusively through **flat structural containment** and **low-contrast outlines**. The system deliberately omits blur, skeuomorphic extrusion, and glow effects to prevent visual ambiguity.

- **Base Layer (Elevation 0):** Background canvas `#14181D`.
- **Panels & Fieldsets (Elevation 1):** Flat `#1B2227` enclosed by a razor-thin `1px solid #2E373F` border.
- **Modals, Flyouts & Overlays (Elevation 2):** Layered `#222B34` with `1px solid #5CA99E` active structural borders. A subdued ambient drop shadow (`0 8px 24px rgba(0, 0, 0, 0.55)`) visually separates top-level layers without casting light blooms or halos.
- **Nested Cells / Code Insets:** Recessed into `#14181D` with `1px solid #2E373F`.

## Shapes
Geometry is strictly orthogonal: every corner is set to `0px` radius.

Buttons, badge containers, modals, table rows, and form elements present completely sharp corners. This zero-radius mandate reinforces the architectural, non-decorative terminal ethos, treating every interface boundary as an exact coordinate in a ledger grid.

## Components

### Buttons
- **Primary Action:** Solid background `#5CA99E`, sharp `0px` corners, text color `#14181D` (bold `JetBrains Mono`), padding `8px 16px`. Hover: `#86BBB4`. Focus: `2px solid #E7E4DC` outline offset by `2px`.
- **Secondary / Utility:** Background `#1B2227`, border `1px solid #2E373F`, text color `#E7E4DC`. Hover: background `#222B34`, border `#5CA99E`.
- **Destructive:** Background `#3A1E1B`, border `1px solid #5A2D28`, text `#F29E94`. Hover: background `#4A2421`.

### Status Badges & Chips
- Defined with `0px` radius, inline-flex, uppercase label tracking (`0.06em`), text size `0.6875rem`, padding `2px 8px`, border `1px solid`.
- Explicit palettes apply per status:
  - *Verified:* Background `#183325`, Border `#234E39`, Text `#7CD5A7`.
  - *Mismatch:* Background `#3A1E1B`, Border `#5A2D28`, Text `#F29E94`.
  - *Revoked:* Background `#362810`, Border `#533E1A`, Text `#E5BA6C`.
  - *Not Found:* Background `#192A3A`, Border `#264057`, Text `#93C2EB`.
  - *Needs Clarification:* Background `#222B34`, Border `#323E4B`, Text `#C0C8D0`.

### Data Tables & Hash Inspection Lists
- Horizontal cell borders `1px solid #2E373F`. Vertical borders between columns optional for terminal comparison modes.
- Header row: `#14181D`, text `#9AA4AD`, font `JetBrains Mono` uppercase `11px`, padding `10px 12px`.
- Row state: Default `#1B2227`. Alternate/Zebra: `#181E23`. Hover: `#222B34`. Selected: `#1E2F2E` with left border `2px solid #5CA99E`.

### Form Inputs & Hash Query Fields
- Background `#14181D`, border `1px solid #2E373F`, text `#E7E4DC`, font `JetBrains Mono`, padding `10px 12px`. Zero radius.
- Placeholder text `#9AA4AD`.
- Focused state: border `1px solid #5CA99E`, absolute shadow omitted.

### Checkboxes & Binary Selectors
- Custom square box `16px x 16px`, background `#14181D`, border `1px solid #2E373F`, `0px` corner radius.
- Checked state: background `#5CA99E`, checked glyph text `#14181D`.

### Panels & Cards
- Container background `#1B2227`, bound by `1px solid #2E373F`. Header band divided by an internal `1px solid #2E373F` border. Zero corner radius throughout.