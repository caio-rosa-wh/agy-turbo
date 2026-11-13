# agy-turbo

Pacote de melhorias para o [Antigravity CLI](https://antigravity.google/docs/cli/reference/) (`agy`), com ideias trazidas de mods do Claude Code. Testado no agy 1.5.7, Linux.

```text
 Gemini 4 Hydrogen  | high  tok 158k/1M (16%) ￭￭￭￭￭･････････････････････  $2.48
 usage  5h ￭￭￭￭￭￭￭￭･････････････････････  26%  7d ￭￭￭￭￭￭￭￭￭￭￭￭￭･･････････････  45%
```

| Parte | Estado | O que faz |
| --- | --- | --- |
| [statusline](statusline/) | ✓ pronto | Statusline de 2 linhas: modelo, esforço, contexto, custo e cotas 5h/7d |
| [prismantis](plugins/prismantis/) | ✓ pronto | Regras de formato + skill `chart` (barras, linhas e funções em Unicode) |
| effortless | planejado | Sugestão de esforço por mensagem (hook `PreInvocation`) |
| [filetree](filetree/) | ✓ preview | Árvore com git status e brilho onde o agente lê/escreve; abre ao lado do `agy` |

## Instalar

Precisa de `agy`, `bash`, `jq` e Python 3 (o filetree cria um venv com Textual).

```bash
git clone <url-deste-repo> agy-turbo && cd agy-turbo
./install.sh                 # tudo
./install.sh statusline      # só a statusline
./install.sh prismantis      # só o plugin
./install.sh filetree        # árvore de arquivos (agy-tree / agy-turbo)
```

O instalador da statusline faz backup do `~/.gemini/antigravity-cli/settings.json` e guarda o `statusLine` anterior. Para desfazer:

```bash
./uninstall.sh               # tudo, restaurando a statusline anterior
```

## Por que não é um port 1:1

Os mods do Claude Code são módulos TSX que rodam dentro do host e redesenham a interface. O agy não carrega módulos. A extensão dele é feita por scripts externos (statusline, hooks) e por plugins com rules, skills, MCP e sidecars. Por isso, cada parte aqui é uma reimplementação da ideia com os recursos que o agy oferece. Detalhes, limites e evidências estão em [docs/arquitetura.md](docs/arquitetura.md).

## Testes

```bash
tests/run.sh
```

Roda a statusline com um payload real do agy e casos de borda, testa install/uninstall numa cópia do settings e faz `agy plugin validate --strict` (este último só onde o `agy` estiver instalado).

## Licença

Veja [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) para os projetos de origem.
