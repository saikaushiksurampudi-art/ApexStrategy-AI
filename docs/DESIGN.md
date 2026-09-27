# Interface & visualisation decisions

## A single dark theme

The app ships one deliberately-chosen dark theme rather than a light/dark
toggle. The reason is specific rather than stylistic: **F1 team colours are
designed for dark backgrounds**, and all twelve clear the 3:1 contrast
threshold against the chart surface `#15161c`:

| Team | Colour | Contrast |
|---|---|---|
| Mercedes | `#27F4D2` | 12.86:1 |
| Sauber | `#52E252` | 10.62:1 |
| Williams | `#64C4FF` | 9.35:1 |
| Haas | `#B6BABD` | 9.24:1 |
| McLaren | `#FF8000` | 7.17:1 |
| RB | `#6692FF` | 6.12:1 |
| Alpine | `#0093CC` | 5.20:1 |
| AlphaTauri | `#5E8FAA` | 5.14:1 |
| Aston Martin | `#229971` | 5.04:1 |
| Ferrari | `#E8002D` | 3.84:1 |
| Red Bull | `#3671C6` | 3.73:1 |
| Alfa Romeo | `#C92D4B` | 3.40:1 |

On a light surface, Mercedes' cyan and Haas' grey fail badly. Shipping a light
mode would mean either unreadable charts or abandoning the team colours that
make the product instantly legible to its audience. One validated theme beats
two, one of which is broken.

---

## Two palettes, two jobs

**Team colours carry entity identity.** An F1 viewer reads McLaren orange and
Ferrari red instantly, and no arbitrary palette can compete with that
recognition.

But team colours are brand colours, not a validated categorical ramp. Several
pairs are not distinguishable under colour-vision deficiency — the two reds
(Ferrari `#E8002D` / Alfa `#C92D4B`), and the several blues (Red Bull, Williams,
RB). So the rule throughout the app is:

> **Identity is never carried by colour alone.** Every team-coloured chart also
> has a legend *and* direct labels, and every colour swatch sits next to the
> name it stands for.

Concretely:

- The constructors' championship line chart labels each line **at its final
  round**, with collision avoidance so teams finishing on similar points do not
  stack their labels on top of each other.
- The drivers' championship bar chart labels every bar with the driver's
  three-letter code.
- Tables carry the team name in text beside the swatch.

**Where the series are not teams**, a validated categorical palette is used
instead — driver A vs driver B in the comparison view, for instance, since both
drivers could be on the same team. These are the dark-mode steps of the
reference palette:

| Slot | Hex |
|---|---|
| 1 | `#3987e5` |
| 2 | `#d95926` |
| 3 | `#199e70` |

Verified against the `#15161c` surface with all pairs in play:

```
[PASS] Lightness band       all 3 inside L 0.48–0.67
[PASS] Chroma floor         all 3 >= 0.1
[PASS] CVD separation       worst pair ΔE 9.4 (deutan)
[PASS] Normal-vision floor  worst pair ΔE 20.9
[PASS] Contrast vs surface  all 3 >= 3:1
```

---

## Chart conventions

Applied uniformly so the product reads as one system:

- **Recessive grid and axes.** Horizontal gridlines only, dashed, in `#2a2e3a`.
- **A hover tooltip on every plotted form**, using one shared tooltip component.
- **A legend whenever there are two or more series**; a single series is named
  by the chart title instead.
- **A Table toggle on every chart.** No chart is the only way to read its
  numbers — this is the relief route for anyone the colours fail, and it is
  useful to everyone else.
- **Thin marks**, 2px lines, 4px rounded bar ends anchored to the baseline.
- **A note under each chart** stating what the data does and does not cover.

### Forms chosen, and why

| View | Form | Reasoning |
|---|---|---|
| Constructors' championship | Multi-line, cumulative | Change over time across entities |
| Drivers' championship | Bar | Magnitude comparison at one moment |
| Podium probabilities | Horizontal meters | Each row is an independent 0–100% value; a shared track makes them directly comparable, and there is no axis to mislead |
| Grid conversion | Bar | Ordered buckets, one measure |
| Pit-stop distribution | Bar | Discrete categories, share of total |
| Finishing positions | Line, reversed Y | Trend where lower is better |
| Championship leader, gap, model version | Stat tiles | One number with no comparison — a chart would be noise |

### Gaps mean missing data

The finishing-position chart uses `connectNulls={false}`. A retirement has no
finishing position, so the line breaks rather than interpolating through it.
Drawing a continuous line across a DNF would invent a data point.

---

## Communicating uncertainty

The interface treats "this is an estimate" as a design requirement, not a
disclaimer to bury:

1. **Every probability view opens with a labelled estimate banner**, not a
   footnote.
2. **Scenarios are badged "Simulation"** in the card header, and their
   disclaimer names exactly what was held constant.
3. **A projected grid is called out.** When qualifying has not run, the UI says
   the grid is projected from recent form.
4. **Factor breakdowns are expandable** on every driver, and state their own
   limitation: features are varied one at a time, so interactions are not
   separated out.
5. **The model's scorecard is a user-facing page** with a "Beats baseline" or
   "Does not beat baseline" badge — a claim the product has to keep earning.
6. **Sample sizes sit next to circuit statistics**, with an explicit note that a
   driver with two starts somewhere has a record, not a trend.
7. **A calibration check is shown on the dashboard**: podium probabilities
   across the field should sum to ≈3.0.

---

## Accessibility

- All body text meets WCAG AA against its surface.
- Colour is never the sole carrier of meaning — see the two-palette rule above.
- Every chart has a table equivalent.
- Interactive controls use real `<button>` and `<select>` elements with
  `aria-pressed` / `aria-expanded` where they toggle.
- Focus rings are visible and use a 2px offset ring.
- Layouts reflow to phone width with no horizontal page scroll.
