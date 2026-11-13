# Reply formatting (prismantis for Antigravity CLI)

Adapted from the prismantis format note (https://github.com/NahumLitvin/prismantis, MIT). This session runs in the Antigravity CLI, which draws markdown itself; there is no plugin renderer.

- The CLI draws markdown headings, lists, links, tables, quotes and fenced code with syntax highlighting. Use them.
- When a reply compares options or lists items with several attributes, use a markdown table.
- Put any command or snippet the user may run or copy in a fenced block with a language tag, never inline code.
- Use GitHub alerts (`> [!NOTE]`, `> [!WARNING]`) for risks and caveats the user must not miss.
- Mermaid is drawn only for `flowchart` and `sequenceDiagram`; every other kind (pie, gantt, xychart-beta, class, state, er) prints as source, so do not use them. Keep diagrams small: `flowchart TD` past 4 steps, at most 4 nodes side by side, labels under 20 characters, no `;`, quotes or HTML in labels; sequence diagrams with at most 4 one-word participants and messages under 16 characters.
- When position carries meaning (a screen layout, phases on a time axis, before/after), draw a text picture in a plain fenced block (```text). It prints exactly as written, with no colors: at most 74 columns, glyphs one column wide such as ─│┌┐└┘├┤┬┴┼═║→←►◄▲▼✓✗●○█▏■□·, no emoji or tabs, and box rows padded to the top border. Draw a time axis with edge ticks like ▏───▏───▏.
- Add a diagram or picture only when a flow or a numeric series is easier to see than read, and never a second picture of what one already shows. Skip them for short or simple answers, code changes and reports. The prose never retells the picture.
- When asked to explain, compare or plan something and a picture would help, build the reply around it, with the core on the first screen as a picture or a sentence.
- `$` opens inline math in this CLI: in prose write a literal dollar as `\$` (prices: \$100); inside code spans and fenced blocks write it bare.
