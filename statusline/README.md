# statusline

Statusline de 2 linhas para o Antigravity CLI (`agy`), com o mesmo layout do Cockpit do Claude Code:

```text
 Gemini 4 Hydrogen  | high  tok 158k/1M (16%) ￭￭￭￭￭･･････････････････････  $2.48
 usage  5h ￭￭￭￭￭￭￭￭･････････････････････  26%  7d ￭￭￭￭￭￭￭￭￭￭￭￭￭･･････････････  45%
```

Implementação própria em bash + `jq`, uma chamada `jq` por execução (~25 ms). Veja `../docs/arquitetura.md` para o payload que o agy envia.

## Instalar / desinstalar

```bash
./install.sh     # backup do settings.json + guarda o statusLine anterior
./uninstall.sh   # restaura o statusLine anterior
```

Testar sem instalar (vale só para esta sessão):

```bash
agy --settings "{\"statusLine\":{\"type\":\"command\",\"command\":\"$PWD/statusline.sh\"}}"
```

Testar offline:

```bash
./statusline.sh < ../docs/evidencias/statusline-stdin-agy-1.5.7.json
```

## De onde vem cada dado

| Mostra | Campo do agy |
| --- | --- |
| modelo | `model.display_name`, sem o sufixo `(High)` |
| esforço | `model.effort` |
| tok | `context_window.total_input_tokens / context_window_size (used_percentage)` |
| custo | `cost`. Só aparece depois do primeiro turno |
| 5h / 7d | `quota.gemini-5h` / `gemini-weekly` para modelos Gemini, `3p-5h` / `3p-weekly` para Claude/GPT. O uso é `1 - remaining_fraction` |

## Opções (variáveis de ambiente)

| Variável | Efeito |
| --- | --- |
| `COCKPIT_RESET=1` | mostra quando cada cota renova (`↻4h00m`) |
| `COCKPIT_STATE=1` | mostra o estado do agente (`running`…) |
| `COCKPIT_QUOTA=gemini\|3p` | força o grupo de cota |
| `COCKPIT_BAR=30` | largura fixa das barras (padrão: ajusta a `terminal_width`) |
| `COCKPIT_ASCII=1` | barras com `#` e `.` |
| `COCKPIT_STACK=true ./statusline/install.sh` | empilha com a statusline padrão do agy (modo, dicas) |
| `NO_COLOR=1` | sem cores |

A barra de contexto e os percentuais de cota ficam vermelhos a partir de 80%.

O agy só roda a statusline de novo quando algo muda na sessão, não por timer. Com o agy ocioso, os números ficam parados até o próximo evento.
