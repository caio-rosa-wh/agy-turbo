# filetree (agy-turbo)

Árvore de arquivos estilo IDE que mostra onde o agente do agy está lendo e escrevendo. Inspirada no [claude-code-filetree](https://github.com/data-goblin/claude-code-filetree) (MIT), reimplementada para o agy.

```text
agy-tree ~/projetos/agy-turbo                          seguindo
⎇ main  6 alterados
▸ docs
▾ plugins
├ ▾ filetree
│ ├ ▾ hooks
│ │ └   collect.py ? +12 -3                        2m     <- brilha laranja: o agente acabou de escrever
│ ├   hooks.json ?                                 2m
▸ statusline
  README.md M                                     13m
escrevendo hooks/collect.py   $ grep -n READ …
```

## Como funciona

O agy não tem painel lateral para plugins, então o filetree tem duas partes:

1. **Hook do plugin:** um `PostToolUse` (`hooks/collect.py`, cerca de 17 ms, só biblioteca padrão) grava em `activity.jsonl` cada arquivo lido (`read_file`, `cat`, `grep`…), escrito (`write_file`, `edit_file`, `rm`, `>`…) ou tocado por `git`, além do último comando.
2. **App `agy-tree`:** uma TUI em Python/[Textual](https://textual.textualize.io/) que roda ao lado do agy. Lê o `activity.jsonl` e o `git status`.

## Uso: só `agy`

Depois da instalação do agy-turbo, digitar `agy` num terminal abre o agy com a árvore à direita. O tmux roda por baixo, sem barra de status e com mouse, e a sessão fecha inteira quando você sai do agy. A configuração automática adiciona ao `~/.bashrc` uma função `agy` (`shell/agy.bash`) que:

- só entra em ação no `agy` interativo: `agy -p`, `agy plugin …`, `agy update` e outros subcomandos vão direto para o binário;
- se você já estiver no tmux, só abre a árvore no painel ao lado;
- passa direto quando o tmux não está instalado.

`AGY_TREE=0 agy` abre o agy puro e `AGY_TREE_WIDTH=40% agy` muda a largura da árvore. Se o agy for aberto dentro do tmux sem a função, o hook `SessionStart` do plugin abre a árvore na primeira mensagem.

## Instalar e usar

```bash
agy plugin install https://github.com/caio-rosa-wh/agy-turbo   # o plugin se configura na 1ª sessão
agy                     # agy + árvore ao lado (via função do shell)
agy-turbo               # o mesmo, chamando o lançador direto
agy-tree [PASTA]        # só a árvore, para usar em outro terminal
```

`agy-turbo` usa o tmux quando ele existe: agy à esquerda e árvore à direita, na mesma janela. Sem tmux, abre a árvore numa janela nova do Ptyxis; com o GNOME, junte as duas com `Super+←` e `Super+→`. Para a árvore ficar na mesma janela:

```bash
sudo apt install tmux
```

## Recursos

- Git status por arquivo e pasta (`M` alterado, `?` novo, `D` apagado), `+linhas -linhas` dos arquivos alterados, branch com `↑ahead ↓behind`
- Atividade do agente: o arquivo brilha por cerca de 1,5 s (roxo para leitura, laranja para escrita, verde para git) e fica com `○`/`●` por 10 s
- Seguir o agente: abre as pastas e rola até o arquivo que ele tocou (`f` liga e desliga)
- Preview com realce de sintaxe (`p`, ou `enter` num arquivo), busca por nome (`s` ou `/`), coluna de idade ou tamanho (`c`)
- Atalhos vim (`j k h l g G`), `o` abre no `$EDITOR` (ou `xdg-open`), `y` copia o caminho, `.` mostra ocultos, `?` mostra a ajuda

## Ainda não portado do original

Treemap, diff dentro do pane, seleção múltipla que vira contexto do agente, `/cd` automático (o agy não deixa hook mudar o cwd nem anexar arquivos ao prompt), guard de arquivos (dá para fazer com `PreToolUse` + `deny`), ícones Nerd Font.
