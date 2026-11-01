# DESIGN.md — Decentralized Record Verifier with NLP Search

Frontend design system and animation spec. Companion to `prd.md`. Stack: plain HTML, CSS, JavaScript (no framework required).

---

## 1. Design intent

**Feel:** a calm, trustworthy records office, not a crypto dashboard. Think university registrar, notary, or a well-made institutional website. Warm paper tones, ink-dark text, one muted accent, and motion that *explains* what the system is doing.

**Three words:** *Assured. Quiet. Precise.*

| Do | Don't |
|---|---|
| Warm off-white surfaces, ink-navy text | Pure white on pure black, neon on dark |
| One muted teal accent used sparingly | Purple-to-blue gradients, rainbow accents |
| Soft, short shadows; thin 1px borders | Glassmorphism, glowing borders, heavy blur |
| Serif headings, clean sans body, mono for hashes | Default system font stack everywhere |
| Motion that shows process (hashing, validation) | Floating blobs, particles, looping pulses |
| Plain, human sentences | "Revolutionize", "next-gen", emoji headings |

---

## 2. Design tokens

### 2.1 Colour

All values are starting points; check contrast (WCAG AA, 4.5:1 for body text) with a checker before final use.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F6F4EF` | `#14181D` | Page background (warm paper / deep slate) |
| `--surface` | `#FFFFFF` | `#1B2127` | Cards, panels |
| `--surface-2` | `#EFECE4` | `#222A31` | Inset areas, table stripes |
| `--border` | `#DDD8CC` | `#2E373F` | 1px hairlines |
| `--text` | `#1F2933` | `#E7E4DC` | Primary text |
| `--text-muted` | `#5B6670` | `#9AA4AD` | Secondary text |
| `--accent` | `#285F5B` | `#6FA8A1` | Primary buttons, links, focus |
| `--accent-hover` | `#1F4D49` | `#86BBB4` | Hover |
| `--accent-soft` | `#E2EEEC` | `#1E2F2E` | Tinted backgrounds |
| `--ink` | `#1B2A41` | `#C9D3E0` | Headings, logo |

**Status colours (always paired text + tinted background + icon, never colour alone):**

| State | Text | Background | Meaning |
|---|---|---|---|
| Verified | `#2F6B4A` | `#E5F0E9` | Hash matches registered fingerprint |
| Mismatch | `#8E3A31` | `#F5E1DD` | File differs from registered file |
| Revoked | `#7A5410` | `#F6ECD6` | Record exists but was revoked |
| Not found | `#34506B` | `#E4EBF2` | No such record ID |
| Needs clarification | `#5B6670` | `#ECEAE3` | Ambiguous request |

Rule: at most **one accent** visible per view; status colours only appear on results.

### 2.2 Typography

| Role | Font | Notes |
|---|---|---|
| Headings | **Source Serif 4** (600) | Institutional, humane |
| UI and body | **IBM Plex Sans** (400/500/600) | Clear, not the usual AI default |
| Hashes, JSON, IDs | **IBM Plex Mono** (400/500) | Always mono for anything machine-like |

| Style | Size / line-height | Weight |
|---|---|---|
| Display (page title) | 40 / 48 px (28 / 36 on mobile) | 600 serif |
| H2 | 28 / 36 | 600 serif |
| H3 | 20 / 28 | 600 sans |
| Body | 16 / 26 | 400 |
| Small / label | 13 / 20 | 500, letter-spacing 0.02em |
| Mono | 14 / 22 | 400 |

Measure: body copy max width **68 characters**. Use `font-variant-numeric: tabular-nums` for timestamps and metrics.

### 2.3 Spacing, radius, elevation

- Base unit 4 px; scale: 4, 8, 12, 16, 24, 32, 48, 72.
- Radius: 6 px (inputs, badges), 10 px (cards), 999 px only for tiny dots.
- Shadows (light): `0 1px 2px rgba(27,42,65,.06)` resting; `0 6px 18px rgba(27,42,65,.08)` raised. No coloured glows.
- Container max width 1120 px; page gutters 24 px (16 px mobile).

---

## 3. Motion system

**Principle:** every animation answers "what just happened?" or "what is happening now?" Nothing animates only for decoration.

### 3.1 Tokens

| Token | Value |
|---|---|
| `--dur-fast` | 120 ms (hover, press) |
| `--dur-base` | 220 ms (state changes) |
| `--dur-slow` | 420 ms (entrances) |
| `--dur-story` | 900–1400 ms (hashing, validation sequences) |
| `--ease-out` | `cubic-bezier(0.22, 1, 0.36, 1)` |
| `--ease-inout` | `cubic-bezier(0.65, 0, 0.35, 1)` |

Animate only `transform` and `opacity` (plus `stroke-dashoffset` on SVG). Honour `prefers-reduced-motion`: replace movement with instant or opacity-only changes.

### 3.2 Signature interactions

| # | Moment | Animation | Purpose |
|---|---|---|---|
| 1 | **Page load** | Sections fade up 12 px, staggered 60 ms | Calm, orderly entrance |
| 2 | **File dropped** | Dropzone border switches from dashed to solid; file chip slides in | Confirms the upload |
| 3 | **Hashing** | A progress hairline fills; the 64-character hash "resolves" left to right from random hex into the final value over ~900 ms | Shows the fingerprint being computed |
| 4 | **Comparison** | Two hashes (computed vs registered) sit side by side; matching characters tint softly in sequence, a mismatch highlights the first differing character | Makes integrity checking visible |
| 5 | **Result seal** | A round seal draws its outline and tick/cross with stroke animation (~600 ms), badge colour fades in | Clear, memorable outcome |
| 6 | **Query parsing** | Typing indicator (three dots, 1.2 s max) is replaced by a JSON panel whose lines reveal one by one | Shows the model's *suggestion* arriving |
| 7 | **Validation pipeline** | A horizontal stepper lights each stage in turn: *Schema → Intent allowlist → Record ID → Role → Contract call*. A failing stage stops with a shake of 4 px and a reason message | Demonstrates that the backend, not the model, decides |
| 8 | **Revocation** | Record timeline gains a new entry that slides down; the status badge cross-fades from Verified to Revoked | Explains state change |
| 9 | **Hover / focus** | Cards lift 2 px with a slightly stronger shadow; buttons darken; focus ring 2 px offset in accent | Responsive feel |
| 10 | **Errors** | Inline message expands (height + opacity); form field outlines in the error colour | Non-alarming feedback |
| 11 | **Loading** | Skeleton blocks with a slow, low-contrast shimmer (1.6 s) | Avoids spinners everywhere |

### 3.3 Reference snippets

```css
:root{
  --dur-fast:120ms; --dur-base:220ms; --dur-slow:420ms;
  --ease-out:cubic-bezier(.22,1,.36,1);
}
.reveal{opacity:0;transform:translateY(12px);
  transition:opacity var(--dur-slow) var(--ease-out),
             transform var(--dur-slow) var(--ease-out);}
.reveal.in{opacity:1;transform:none;}

/* seal tick */
.seal path{stroke-dasharray:60;stroke-dashoffset:60;
  animation:draw 600ms var(--ease-out) 150ms forwards;}
@keyframes draw{to{stroke-dashoffset:0}}

@media (prefers-reduced-motion:reduce){
  *{animation-duration:1ms!important;transition-duration:1ms!important;}
  .reveal{transform:none}
}
```

```js
// staggered reveal
const io = new IntersectionObserver((entries)=>{
  entries.forEach((e,i)=>{ if(e.isIntersecting){
    e.target.style.transitionDelay = `${i*60}ms`;
    e.target.classList.add('in'); io.unobserve(e.target);
  }});
},{threshold:.15});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

// hash "resolve" effect (display-only; real hash computed separately)
function resolveHash(el, finalHex, ms=900){
  const hex='0123456789abcdef', start=performance.now();
  (function tick(now){
    const t=Math.min((now-start)/ms,1), locked=Math.floor(t*finalHex.length);
    el.textContent=finalHex.slice(0,locked)+
      Array.from({length:finalHex.length-locked},()=>hex[Math.random()*16|0]).join('');
    if(t<1) requestAnimationFrame(tick);
  })(start);
}
```

---

## 4. Layout and pages

Global shell: slim top bar (wordmark left, nav centre/right, theme toggle), main content in a 1120 px container, quiet footer with the integrity disclaimer.

**Wordmark:** "Record Verifier" in Source Serif 4 with a small round seal mark (outline, 1.5 px stroke). No gradient logo.

### 4.1 Verify File (home)

```
┌──────────────────────────────────────────────────────┐
│ ◯ Record Verifier        Verify  Ask  Admin  Results │
├──────────────────────────────────────────────────────┤
│  Check a certificate against its registered record   │
│  Plain subtitle (1 line)                             │
│                                                      │
│  ┌────────────── card ──────────────────────────┐   │
│  │ Record ID  [ CERT-104        ]                │   │
│  │ ┌ dashed dropzone: drop PDF or browse ┐       │   │
│  │ [ Verify file ]                               │   │
│  └───────────────────────────────────────────────┘   │
│  ┌ result card (appears) ───────────────────────┐   │
│  │ (seal)  Verified   · computed vs registered   │   │
│  │ hash A  ████…       hash B  ████…             │   │
│  └───────────────────────────────────────────────┘   │
│  Footer note: a match proves file integrity only.    │
└──────────────────────────────────────────────────────┘
```

### 4.2 Ask a Question

Two-column on desktop (stacked on mobile):
- **Left:** a single input ("Ask about a certificate…") with 3 example chips; answer card below.
- **Right:** "How the request was handled" panel: parsed JSON (mono, syntax-tinted in muted tones) and the validation pipeline stepper (motion #6 and #7).

### 4.3 Admin

Login card, then a two-tab view: **Register** (ID, file or hash, metadata) and **Revoke** (ID, reason). Confirm dialogs use plain wording ("Revoke CERT-104? This cannot be undone."). Role badge always visible when logged in.

### 4.4 Results (evaluation)

Table of test cases TC-01…TC-10 with pass/fail badges; a small comparison block for SLM vs rules baseline (accuracy, rejection rate, latency) using horizontal bars in `--accent` and `--text-muted` only. Footer: "Measured on synthetic data; see limitations."

---

## 5. Component spec

| Component | Spec |
|---|---|
| **Button (primary)** | Accent fill, white text, 6 px radius, 44 px min height; hover darken; press `translateY(1px)`; disabled 50 % opacity |
| **Button (secondary)** | Transparent, 1 px border, ink text |
| **Input** | 44 px height, 1 px border, 2 px accent focus ring; label above, helper text below |
| **Dropzone** | Dashed 1.5 px border, `--surface-2` fill; hover/drag tints `--accent-soft`; shows filename, size, remove link |
| **Status badge** | Icon + text, tinted background, 13 px label, 6 px radius |
| **Result card** | Seal (56 px), status title (serif), one-line explanation, two hash blocks in mono with copy buttons |
| **Hash block** | Mono, grouped in 8-character chunks for readability, subtle `--surface-2` background |
| **JSON viewer** | Mono, muted key/value colours (slate, teal, ochre), no bright syntax colours |
| **Pipeline stepper** | 5 small nodes joined by a hairline; states: idle / active / passed / failed |
| **Timeline** | Vertical hairline, small filled dots, timestamp (tabular), event text |
| **Toast** | Bottom-right, surface background, 1 px border, auto-dismiss 4 s, `aria-live="polite"` |
| **Table** | Zebra with `--surface-2`, sticky header, 13 px uppercase-free labels |
| **Empty state** | One sentence + one action; no illustrations required |
| **Skeleton** | `--surface-2` blocks with slow shimmer |

**Icons:** inline SVG, 1.5 px stroke, 20 px (Lucide-style outline). No emoji as UI icons.

---

## 6. Microcopy (human tone)

| Situation | Text |
|---|---|
| Verified | "This file matches the registered record." |
| Mismatch | "This file doesn't match the registered version. It may have been edited or re-saved." |
| Revoked | "This record was revoked on 12 Dec 2026." |
| Not found | "We couldn't find a record with that ID." |
| Needs clarification | "Which certificate do you mean? Please include its ID, for example CERT-104." |
| Refused request | "That request isn't something this tool can do." |
| Service down | "The blockchain isn't reachable right now. This isn't a verification result. Please try again." |
| Footer disclaimer (always visible near results) | "A match shows the file is identical to what was registered. It doesn't prove who issued it or that its contents are true." |

Voice: plain, short sentences, no jargon on public pages; technical detail lives in the "How this was handled" panel.

---

## 7. Accessibility and responsiveness

- WCAG AA contrast; status never conveyed by colour alone.
- Full keyboard use; visible focus ring; logical tab order; skip-to-content link.
- Results announced with `aria-live="polite"`; dropzone is a real `<button>`/`<input type="file">`.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`; manual theme toggle persisted in memory for the session.
- Breakpoints: 640 (mobile), 900 (tablet), 1120 (desktop). Touch targets ≥ 44 px.
- Hashes wrap or scroll inside their own container, never break the page.

---

## 8. Implementation notes

```
/frontend
  index.html        (Verify)
  ask.html
  admin.html
  results.html
  /css  tokens.css  base.css  components.css  motion.css
  /js   app.js  hash-effect.js  pipeline.js  api.js
  /assets  icons.svg  seal.svg
```

- Load fonts from Google Fonts with `display=swap` and fallbacks (`Georgia`, `system-ui`, `ui-monospace`).
- Single `tokens.css` holds all variables; dark theme via `@media (prefers-color-scheme: dark)` plus a `[data-theme]` override.
- The hash "resolve" effect is **display only**; the real SHA-256 and the comparison come from the backend response.
- The pipeline stepper must reflect the *actual* backend validation results returned by the API, not a scripted demo.
- Performance: no animation libraries required; keep first load under a few hundred KB excluding fonts.

---

## 9. Quality checklist

- [ ] No neon, no gradients on text, no glow shadows
- [ ] One accent colour per view
- [ ] Every animation has a purpose from §3.2
- [ ] Reduced-motion tested
- [ ] Integrity-only disclaimer visible on all result screens (PRD FR-05)
- [ ] Mono font used for all hashes, IDs and JSON
- [ ] Error states distinguish "not found" from "service unavailable" (PRD FR-04, TC-08)
- [ ] Looks credible in both light and dark themes
