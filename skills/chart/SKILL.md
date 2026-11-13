---
name: chart
description: >-
  Draws bar, horizontal bar, line, sparkline and math-function charts as Unicode text the Antigravity CLI shows
  inside a ```text block. Use this skill whenever a reply would benefit from a chart of numbers (a series over
  time, values across categories, comparing series) or the user asks to plot or graph something, such as cos(x).
---

# Chart

The CLI does not draw bar or line charts (mermaid xychart prints as source). Generate the chart with the bundled
script and paste its output, unchanged, into a ```text block in the reply.

## Steps

1. Run [chart.py](./scripts/chart.py) with `python3` (standard library only). The installed copy is at
   `~/.gemini/config/plugins/agy-turbo/skills/chart/scripts/chart.py`.

   ```bash
   S=~/.gemini/config/plugins/agy-turbo/skills/chart/scripts/chart.py
   python3 $S bar   --title "ALB 5xx por 5 min" --labels 12:09,12:24,12:39 --values 2,4,82
   python3 $S hbar  --labels api,web,db --values 120,45,300 --unit ms
   python3 $S line  --labels jan,fev,mar,abr --series "east:3,5,4,8" --series "west:1,2,6,5"
   python3 $S func  --expr "cos(x)" --from 0 --to 2*pi --title "f(x) = cos(x)"
   python3 $S spark --values 1,5,2,8,3
   ```

   - `func` accepts `x`, numbers, `+ - * / ** %` and math functions (`sin cos tan exp log sqrt abs pi e`…).
     Ranges written with `pi` get π axis labels.
   - `--width` (10-100, default 60) and `--height` (4-30, default 12). Keep the chart at most 74 columns wide
     for narrow terminals: about `--width 60` for line/func and up to 9 bars for `bar`.
   - Use `bar` for up to ~10 categories, `hbar` for long labels or many categories, `line` for series over time
     (several `--series` get distinct markers and a legend), `spark` for an inline trend.
2. Copy the output exactly into a ```text block. Do not redraw, align or "fix" it by hand.
3. Add one short sentence with the takeaway (peak, trend, anomaly); do not retell every value. Use a markdown table
   instead when exact values matter more than the shape.

## Check

The output must start with the title (if given) and end with the x-axis labels. If the script prints a
`ValueError`, fix the arguments (same number of labels and values; allowed expression) and run it again.
