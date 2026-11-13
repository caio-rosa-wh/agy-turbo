# prismantis (agy-turbo)

Plugin do agy que instrui o modelo a responder com tabelas, alertas, blocos de código com linguagem e diagramas que o **próprio Antigravity CLI desenha**. É o mesmo caminho que o autor do [prismantis](https://github.com/NahumLitvin/prismantis) seguiu no port para o Codex: no agy, plugins não redesenham a interface.

Conteúdo: `rules/AGENTS.md`, adaptado da nota de formato do prismantis (MIT). As diferenças em relação ao original:

- Mermaid só com `flowchart` e `sequenceDiagram`, os tipos que o agy desenha na conversa. Pie, gantt e xychart aparecem como código.
- Figuras viram blocos ` ```text ` sem marcação de cor `{role:...}`.
- Aviso sobre `$`, que abre matemática inline no agy.

```bash
agy plugin install ./plugins/prismantis
```

## Skill `chart`

O agy não desenha gráficos de barra nem de linha. A skill `chart` (`skills/chart/scripts/chart.py`, só biblioteca padrão do Python) gera esses gráficos em Unicode, e o modelo cola a saída num bloco ` ```text `. Tipos:

- `bar`: barras verticais, com o valor em cima, e suporte a negativos
- `hbar`: barras horizontais
- `line`: linhas em braille, com várias séries, marcadores e legenda
- `func`: função de `x`, com eixo em múltiplos de π
- `spark`: tendência numa linha só

```bash
python3 plugins/prismantis/skills/chart/scripts/chart.py func --expr "cos(x)" --from 0 --to 2*pi
```

`--expr` não usa `eval`: a expressão é validada por AST e só aceita números, `x`, operadores e funções de `math`. Os gráficos saem sem cor, porque o agy mostra blocos de código como texto puro.
