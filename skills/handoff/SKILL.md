---
name: handoff
description: >-
  Writes HANDOFF.md so the work can continue in a fresh conversation with an empty context. Use when the user asks
  for a handoff, to "continue in a new chat", to start over clean, or when the agy-turbo status line suggests a
  handoff because the context is large and the topic changed.
---

# Handoff

Write `HANDOFF.md` at the root of the current workspace, then tell the user how to continue.

## Steps

1. Gather the facts (do not guess): run `git status --short` and `git log --oneline -5` if it is a git repo, and
   list the files you created or changed in this conversation.
2. Write `HANDOFF.md` in the user's language with these sections, short and concrete:
   - **Objetivo / Goal**: what the user wants, in one or two sentences.
   - **Estado / State**: what is done and verified, and what is not.
   - **Decisões / Decisions**: choices made and why, including what the user approved or rejected.
   - **Arquivos / Files**: paths touched, one line each on what changed.
   - **Próximos passos / Next steps**: numbered, the first one ready to execute.
   - **Como validar / How to verify**: commands or checks.
   - **Cuidados / Watch out**: open risks, credentials not to touch, pending approvals.
3. Tell the user: exit with `/exit` (or Ctrl+C twice) and run `agy` again in the same folder. agy-turbo injects
   `HANDOFF.md` into the new conversation automatically (once, within 48 hours).

Do not include secrets, tokens or passwords in `HANDOFF.md`. If one appeared in the conversation, name it without
its value.
