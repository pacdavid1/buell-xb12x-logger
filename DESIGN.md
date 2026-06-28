# Buell Logger — Design System

> Project-specific design tokens and component rules.
> Extends the mono skill (monospace-driven, high-contrast, compact density).
> All code and UI text must be in English.

---

## Design Tokens

### Color Palette

```css
:root {
  /* Surfaces */
  --bg:  #0a0a0b;   /* page background — deepest layer */
  --p:   #111114;   /* panel / card background */
  --bd:  #1e1e24;   /* border / divider */

  /* Text */
  --tx:  #c8c8cc;   /* primary text */
  --dm:  #55555e;   /* dimmed / label / secondary text */

  /* Accent — action and highlight */
  --ac:  #e8420a;   /* primary accent — orange-red (buttons, active borders, break line) */
  --a2:  #f5a623;   /* secondary accent — amber (warnings, gear labels, section headers) */
  --bl:  #3d9eff;   /* info / link / download */
  --gn:  #2cdd6e;   /* positive / success / high confidence */
  --rd:  #ff4444;   /* negative / error / danger */

  /* Typography */
  --mn:  'Share Tech Mono', monospace;   /* data, labels, buttons, all UI text */
}
```

### Metric chart colors (Canvas only)
```
PW avg:   #e8420a   (2.5px solid)
PW1:      #3d9eff   (1.2px dashed)
PW2:      #2cdd6e   (1.2px dashed)
RPM:      #ffc832   (1.5px solid)
VSS:      #b464ff   (1.5px solid)
TPS:      #50c8c8   (1.5px solid)
AE:       #c084fc
Alt:      #84cc16
```

---

## Typography

| Use | Font | Size | Weight | Color |
|-----|------|------|--------|-------|
| Body / UI prose | Barlow Condensed, sans-serif | 14px | 400 | --tx |
| All data, labels, buttons, mono | Share Tech Mono | 7–13px | 700 for buttons | --tx / --dm |
| Section labels | Share Tech Mono | 7px | 700 | --a2, letter-spacing .12em, uppercase |
| Chart axis labels | monospace (canvas) | 6–7px | — | --dm at 0.45–0.5 alpha |
| Header title | Share Tech Mono | 13px | 900 | #fff, letter-spacing .04em |

Font size scale: 7 → 8 → 9 → 10 → 11 → 13 → 14px. No other sizes.

---

## Spacing & Layout

- Border radius: **2px** everywhere. Never more.
- Padding scale: 1px 4px (badges) → 3px 8px (small buttons) → 4px 10px (chips) → 5px 8px (cond-box) → 6px 12px (controls bar, header)
- Gap scale: 3px → 5px → 6px → 8px → 12px
- Scrollbars: width/height 3px, transparent track, `--bd` thumb
- All pages: `height: 100dvh`, `overflow: hidden`, column flex

---

## Components

### Header
```
height: auto, padding 6px 12px
background: --p
border-bottom: 2px solid --ac   ← signature orange stripe
flex: space-between, align center
title: Share Tech Mono 13px 900 #fff
nav links: 9px --dm, border 1px --bd, padding 3px 8px, radius 2px
nav link active: color --ac, border-color --ac
nav link hover: color --bl, border-color --bl
```

### Controls Bar
```
background: --p, border-bottom 1px --bd, padding 6px 12px
flex row, gap 8px, flex-wrap wrap
labels: 7px --a2 uppercase letter-spacing .12em
selects: background --bg, border 1px --bd, color #fff, 10px, padding 4px 6px, radius 2px
primary button (LOAD/COMPARE): --ac background, #fff text, 10px 700 uppercase, padding 6px 14px, radius 2px
secondary button (download): --bl background
disabled: opacity .4
```

### Chip Strip (horizontal scrollable cluster list)
```
background: --bg, border-bottom 1px --bd, padding 5px 12px
overflow-x auto, white-space nowrap
chip: inline-flex, gap 6px, padding 4px 10px
      border 1px --bd, border-left 3px transparent, radius 2px
      background --p, font 9px --mn, color --dm
chip hover: border-color --bl, color --tx
chip active: border-left-color --ac, border-color --ac, color #fff
gear label inside chip: 14px 900 --a2
N badge: 11px 900 — hi=--gn, md=--a2, lo=--dm
```

### Badge (cb)
```
font: --mn 7px, padding 1px 4px, radius 1px, border 1px solid
cb-ok:    color --gn,  border rgba(44,221,110,.3)
cb-warn:  color --a2,  border rgba(245,166,35,.3)
cb-info:  color --dm,  border --bd
cb-alert: color --rd,  border rgba(255,68,68,.3)
```

### Cond-Box (condition summary card)
```
background --p, border 1px --bd, radius 2px, padding 5px 8px, min-width 130px, flex 1
label: --mn 7px --dm uppercase letter-spacing .12em, margin-bottom 3px
row: flex space-between, --mn 9px, padding 1px 0, gap 8px
  key: --dm
  value: #fff 700
```

### Chart Area (Canvas)
```
flex 1, min-height 0, padding 8px 12px 6px, gap 5px
canvas: position absolute, 100%×100%
background: #0a0a0b
Bucket A zone: rgba(255,255,255,0.03) shaded, label "BUCKET A" at 20% alpha
Break line: --ac 50% dashed [4,4], label "BREAK" --ac 70%
Grid lines: rgba(255,255,255,0.035) horizontal
Pre-break curves: 65% alpha, 1.5–2px solid, endpoint dot at break
Post-break avg: 90–100% alpha, 1.5–2.5px, endpoint dots
Confidence band: rgba(--ac, confidence×0.13) fill
```

### Metric Toggle Button
```
inline-flex, gap 4px, padding 3px 9px, border 1px --bd, radius 2px
background --bg, --mn 9px, color --dm
dot: 7px circle, background --mc (metric color) when active, --dm when off
active: border-color --mc, color --mc, background color-mix(--mc 10%, transparent)
hover: border-color --mc, color --mc
```

### Members Table
```
max-height 90px, overflow-y auto, border-top 1px --bd
font: --mn 8px, border-collapse collapse
thead: background --p, sticky top 0, z-index 1
th: 7px --dm 700 uppercase, padding 3px 5px, border-bottom 1px --bd, text-align right
td: padding 2px 5px, border-bottom rgba(255,255,255,.03)
row hover: background rgba(255,255,255,.02)
event color dot: 7–8px circle, hsla(hue,70%,60%,0.9)
positive delta: --gn  |  negative delta: --rd
```

### Status Line
```
--mn 9px --dm, margin-left auto
.ok: --gn  |  .err: --rd  |  .loading: --a2
```

---

## Navigation (Hamburger / Nav Bar)

Every page must include identical header nav links:
```
Dashboard | Sessions VS | Launch | Events | (active page highlighted --ac)
```
All links: --mn 9px --dm, border 1px --bd, padding 3px 8px, radius 2px
Active: color --ac, border-color --ac
Hover: color --bl, border-color --bl

---

## Canvas Chart Rules

- Always use `devicePixelRatio` for crisp rendering on retina/mobile
- Margins: TM=14, BM=20, LM=8, RM=8 (tight — data is protagonist)
- Font: `'7px monospace'` or `'bold 7px monospace'` (canvas ignores CSS vars)
- Redraw on `window resize` (debounced)
- Dot endpoints on avg lines: 3px filled circle, same color as line
- globalAlpha: reset to 1.0 after every draw operation

---

## Anti-Patterns

- **Never** use border-radius > 2px
- **Never** use fonts other than Barlow Condensed (prose) or Share Tech Mono (data/UI)
- **Never** add drop shadows or gradients
- **Never** use color outside the defined palette without extending tokens
- **Never** use Spanish in code, labels, or UI strings
- **Never** leave a page without the standard header nav
- **Never** inline font-size values outside the defined scale (7/8/9/10/11/13/14px)
- **Never** use margins for layout — use flex gap

---

## QA Checklist (per page)

- [ ] CSS variables defined in `:root` block at top of `<style>`
- [ ] Header nav present with all links, active page highlighted
- [ ] All text uses --mn (Share Tech Mono) for data/labels, Barlow Condensed for prose
- [ ] All buttons: radius 2px, --mn 10px 700 uppercase
- [ ] Canvas redraws on resize with devicePixelRatio
- [ ] Mobile: touch targets ≥ 32px, no horizontal overflow
- [ ] All UI strings in English
- [ ] Status messages use .ok / .err / .loading classes
- [ ] No raw hex colors outside token definitions
