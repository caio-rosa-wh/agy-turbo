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

## Instalar (um comando)

Pré-requisitos: o [agy](https://antigravity.google/docs/cli/reference/) instalado e logado, além de `tmux`, `jq` e Python 3 com venv. No Ubuntu/Debian:

```bash
sudo apt install -y tmux jq python3-venv
```

Depois, o plugin:

```bash
agy plugin install https://github.com/caio-rosa-wh/agy-turbo
```

É só isso. Na **primeira mensagem** de uma sessão do agy, o plugin se configura sozinho, em segundo plano, em cerca de 30 s na primeira vez por causa do download do Textual:

1. cria um venv com [Textual](https://textual.textualize.io/) para a árvore (`~/.local/share/agy-turbo/venv`);
2. cria os comandos `agy-tree`, `agy-turbo`, `agy-effortless` e `agy-turbo-uninstall` em `~/.local/bin`;
3. aponta o `statusLine` do agy para a statusline do turbo e guarda a anterior;
4. adiciona ao `~/.bashrc` (e ao `~/.zshrc`, se existir) uma função `agy` que abre o agy com a árvore ao lado;
5. lê os modelos e os níveis de esforço disponíveis.

Tudo o que é alterado ganha backup (`*.agy-turbo.bak.*`). Para pular algum passo, defina antes `AGY_TURBO_STATUSLINE=0`, `AGY_TURBO_SHELL=0` ou `AGY_TURBO_TREE=0`. A partir de um clone, `./install.sh` faz o mesmo e já roda a configuração na hora.

### Validar em 1 minuto

1. Rode `agy`, mande qualquer mensagem (por exemplo "oi") e espere a linha roxa **"agy-turbo pronto"** aparecer na statusline.
2. Feche o agy, **abra um terminal novo** e rode `agy` de novo. A árvore de arquivos deve abrir à direita, com o cursor no agy.
3. Peça "leia o README e resuma". O `README.md` brilha na árvore.
4. Peça "faça um gráfico de barras com 3, 7 e 5". A resposta vem com o gráfico em texto.
5. Peça algo pesado ("investigue um deadlock …"). A terceira linha da statusline mostra o esforço mudando e o motivo.

Se algo falhar, mande o conteúdo de `~/.gemini/antigravity-cli/plugin_data/agy-turbo/bootstrap.log`.

## Desinstalar

```bash
agy-turbo-uninstall
```

Restaura a statusline anterior, remove a função `agy` do shell e os comandos, e desinstala o plugin.

## Como usar

- `agy`: abre com a árvore à direita. O tmux roda por baixo, sem barra e com mouse, e a sessão fecha junto com o agy. `agy -p`, `agy plugin …` e outros subcomandos não passam por ele. `AGY_TREE=0 agy` abre o agy puro.
- **effortless:** fica ligado por padrão e funciona assim:
  - **Ao enviar:** as regras locais decidem na hora. Um pedido explícito ("esforço alto", "max effort") ou um sinal claro de tarefa pesada com esforço baixo faz o plugin digitar `/effort X` e reenviar a mensagem, então o novo nível já vale para ela. Nesse caso a mensagem aparece duas vezes no histórico.
  - **Durante o turno:** o juiz Flash avalia em segundo plano. Se pedir mais esforço, o plugin digita `/effort` e as próximas chamadas do turno já sobem.
  - **No fim do turno:** desce o esforço quando for o caso. Se o contexto passou de 80%, roda `/compact` sozinho. Se o juiz viu troca de assunto com contexto acima de 40%, recomenda `/handoff`.
  - **Configurar:** `/effortless` no agy, ou `agy-effortless` no shell (`off`, `judge local`, `floor`, `ceiling`, `economy`, `compact auto|suggest|off`, `handoff suggest|auto|off`).
  - **Atenção:** o `/effort` do agy fica salvo nas configurações, então o último esforço escolhido vale na próxima vez que você abrir o agy.
- `/handoff`: grava `HANDOFF.md`. Na próxima conversa na mesma pasta, o plugin injeta o arquivo como contexto.
- `/compact`: é nativo do agy. O effortless chama sozinho quando o contexto enche (`agy-effortless compact suggest` só avisa).
- Árvore: `?` mostra os atalhos (`p` preview, `s` busca, `f` seguir o agente, `c` coluna, `.` ocultos).

## Limites honestos

- **Juiz Flash:** roda em segundo plano, sem segurar a mensagem, e leva cerca de 7 a 11 s. Quando pede mais esforço, as próximas chamadas daquele turno já sobem. Numa resposta curta, de uma chamada só, o veredito chega tarde e não muda aquela resposta. Pedidos explícitos e sinais claros de tarefa pesada são decididos na hora pelas regras locais.
- **Cache:** o agy informa os tokens lidos do cache por chamada, mas não por quanto tempo o cache vale. A contagem é uma estimativa: 5 min para Gemini e 60 min para Claude, ajustável com `AGY_CACHE_TTL_MIN`.
- **Interface:** o agy não deixa plugins desenharem dentro da TUI dele. Por isso a árvore roda num painel tmux, a troca de esforço digita `/effort` nesse painel, e as respostas usam o renderer nativo, sem cores próprias nos gráficos.
- **Statusline:** só redesenha quando algo muda na sessão. A barra do effortless também aparece ao vivo no rodapé da árvore.

Detalhes técnicos e evidências: [docs/arquitetura.md](docs/arquitetura.md). Projetos de origem: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Testes

```bash
tests/run.sh
```
