# prismantis (agy-turbo)

Plugin do agy que instrui o modelo a responder com tabelas, alertas, blocos de código com linguagem e diagramas que o **próprio Antigravity CLI desenha**. É o mesmo caminho que o autor do [prismantis](https://github.com/NahumLitvin/prismantis) seguiu no port para o Codex: no agy, plugins não redesenham a interface.

Conteúdo: `rules/AGENTS.md`, adaptado da nota de formato do prismantis (MIT). As diferenças em relação ao original:

- Mermaid só com `flowchart` e `sequenceDiagram`, os tipos que o agy desenha na conversa. Pie, gantt e xychart aparecem como código.
- Figuras viram blocos ` ```text ` sem marcação de cor `{role:...}`.
- Aviso sobre `$`, que abre matemática inline no agy.

```bash
agy plugin install ./plugins/prismantis
```
