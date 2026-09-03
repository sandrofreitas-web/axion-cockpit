---
name: code-review
description: >
  Revisa pull requests, diffs ou arquivos staged seguindo um checklist de
  segurança, legibilidade e estilo. Use sempre que o usuário pedir para
  revisar código, comentar um PR, ou avaliar mudanças antes de merge —
  mesmo que ele não use a palavra "review" explicitamente (ex: "dá uma
  olhada nesse diff", "isso tá pronto pra subir?").
tags: [dev, review, git]
compatible_with: [claude, cursor, windsurf, copilot, antigravity]
status: stable
version: "1.0"
---

# Code Review

Revisão objetiva de código, priorizada por severidade.

## Quando usar

- "revisa esse PR / diff / branch"
- "isso tá pronto pra subir?"
- staged changes antes de commit

## Como fazer

1. Rode o linter do projeto, se existir (`package.json` scripts, `Makefile`,
   `pyproject.toml`), antes de revisar manualmente.
2. Classifique cada achado por severidade:
   - **Bloqueante**: bug, falha de segurança, quebra de contrato de API
   - **Importante**: legibilidade, duplicação, falta de teste em caminho crítico
   - **Sugestão**: estilo, nomenclatura, micro-otimização
3. Para cada achado: arquivo:linha, o problema, e a sugestão concreta
   (trecho de código, não só descrição).
4. Termine com um resumo: aprovar / aprovar com ressalvas / bloquear.

## Notas de portabilidade

Nenhuma — skill puramente de raciocínio, funciona igual em qualquer LLM com
acesso ao diff.
