---
name: effortless
description: >-
  Shows or changes agy-turbo's automatic reasoning effort (effortless): turn it on or off, pick the judge (flash
  LLM or local rules), set a floor or ceiling, economy mode. Use when the user types /effortless, asks why the
  effort changed, or wants automatic effort on, off or limited.
---

# effortless

agy-turbo picks the reasoning effort of each message (judge + `/effort`), shows it on the status line and in the
file tree footer. Settings live in a small CLI:

```bash
agy-effortless                    # status and the last decision with its reason
agy-effortless on | off
agy-effortless judge flash | local
agy-effortless floor medium       # never below; ceiling works the same way
agy-effortless economy on         # never above medium
agy-effortless resubmit off       # raise effort from the next message instead of re-sending the current one
agy-effortless reset
```

Run the command the user asked for (or `agy-effortless` to show status) and report the output in one line.
If `agy-effortless` is not found, run `~/.gemini/config/plugins/agy-turbo/bin/agy-effortless`.
