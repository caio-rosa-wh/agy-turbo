# agy-turbo

Pacote de melhorias para o [Antigravity CLI](https://antigravity.google/docs/cli/reference/) (`agy`). Inspirado em mods do Claude Code e reimplementado para o agy. Testado no agy 1.5.7, Linux.

```text
 Gemini 4 Hydrogen  | high  tok 158k/1M (16%) ￭￭￭￭￭･････････････････････  $2.48
 usage  5h ￭￭￭￭￭￭￭￭･････････････････････  26%  7d ￭￭￭￭￭￭￭￭￭￭￭￭￭･･････････････  45%
 ✦ high · cache ~4m · 16% context   low medium [ high ] xhigh   auto · Flash: depuração em vários arquivos
```

| Parte | O que faz |
| --- | --- |
| **statusline** | Modelo, esforço, contexto, custo e cotas 5h/7d, mais a linha do effortless |
| **filetree** | Árvore de arquivos ao lado do agy, com git status e brilho onde o agente lê ou escreve |
| **prismantis** | Regras de formato (tabelas, alertas, código, diagramas) e skill `chart` (barras, linhas e funções em Unicode) |
| **effortless** | Escolhe o esforço de cada mensagem (juiz Flash) e troca sozinho; cache, contexto, `/handoff` e dica de `/compact` |

## Instalar

Precisa de `agy`, Python 3, `jq` e `tmux` (o tmux é para a árvore ao lado e para a troca automática de esforço).

```bash
agy plugin install https://github.com/caio-rosa-wh/agy-turbo
```

Na primeira mensagem de uma sessão do agy, o plugin se configura sozinho, em segundo plano:

1. cria um venv com [Textual](https://textual.textualize.io/) para a árvore (`~/.local/share/agy-turbo/venv`);
2. cria os comandos `agy-tree`, `agy-turbo`, `agy-effortless` e `agy-turbo-uninstall` em `~/.local/bin`;
3. aponta o `statusLine` do agy para a statusline do turbo e guarda a anterior;
4. adiciona ao `~/.bashrc` (e ao `~/.zshrc`, se existir) uma função `agy` que abre o agy com a árvore ao lado;
5. lê os modelos e os níveis de esforço disponíveis.

Tudo o que é alterado ganha backup (`*.agy-turbo.bak.*`). Quando termina, a statusline avisa: abra um terminal novo e rode `agy`. Para pular algum passo, defina antes `AGY_TURBO_STATUSLINE=0`, `AGY_TURBO_SHELL=0` ou `AGY_TURBO_TREE=0`.

A partir de um clone, `./install.sh` faz o mesmo e já roda a configuração na hora.

## Desinstalar

```bash
agy-turbo-uninstall
```

Restaura a statusline anterior, remove a função `agy` do shell e os comandos, e desinstala o plugin.

## Como usar

- `agy`: abre com a árvore à direita. O tmux roda por baixo, sem barra e com mouse, e a sessão fecha junto com o agy. `agy -p`, `agy plugin …` e outros subcomandos não passam por ele. `AGY_TREE=0 agy` abre o agy puro.
- **effortless:** fica ligado por padrão.
  - Para subir o esforço, ele digita `/effort X` e reenvia a sua mensagem, então o novo nível vale já para ela. A mensagem aparece duas vezes no histórico.
  - Para descer, ele espera o fim do turno.
  - Use `/effortless` no agy, ou `agy-effortless` no shell, para ligar, desligar ou ajustar (`judge local`, `floor`, `ceiling`, `economy`).
- `/handoff`: grava `HANDOFF.md`. Na próxima conversa na mesma pasta, o plugin injeta o arquivo como contexto.
- `/compact`: é nativo do agy. A statusline sugere quando o contexto passa de 80%.
- Árvore: `?` mostra os atalhos (`p` preview, `s` busca, `f` seguir o agente, `c` coluna, `.` ocultos).

## Limites honestos

- **Juiz Flash:** cada mensagem espera de 7 a 11 s antes de começar, cerca de 2,6 s de partida do `agy -p` mais a resposta do Flash. Com `agy-effortless judge local`, as regras locais decidem na hora.
- **Cache:** o agy informa os tokens lidos do cache por chamada, mas não por quanto tempo o cache vale. A contagem é uma estimativa: 5 min para Gemini e 60 min para Claude, ajustável com `AGY_CACHE_TTL_MIN`.
- **Interface:** o agy não deixa plugins desenharem dentro da TUI dele. Por isso a árvore roda num painel tmux, a troca de esforço digita `/effort` nesse painel, e as respostas usam o renderer nativo, sem cores próprias nos gráficos.
- **Statusline:** só redesenha quando algo muda na sessão. A barra do effortless também aparece ao vivo no rodapé da árvore.

Detalhes técnicos e evidências: [docs/arquitetura.md](docs/arquitetura.md). Projetos de origem: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Testes

```bash
tests/run.sh
```
