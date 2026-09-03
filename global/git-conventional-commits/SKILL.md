---
name: git-conventional-commits
description: >
  Padronização rigorosa de mensagens de commit seguindo a especificação Conventional Commits v1.0.0.
  Define tipos semânticos (feat, fix, refactor, perf, docs, chore, test), escopos padronizados,
  mensagens imperativas e marcação de Breaking Changes para geração automatizada de Changelog e SemVer.
tags: [git, commits, conventional-commits, semver, workflow, dev]
globs: [".git/*", "COMMIT_EDITMSG", "CHANGELOG.md"]
compatible_with: [claude, gemini, cursor, windsurf, copilot, antigravity]
status: stable
version: "1.0.0"
---

# Git Conventional Commits Specification

> [!IMPORTANT]
> Toda mensagem de commit DEVE seguir estritamente o formato estruturado do **Conventional Commits v1.0.0** em minúsculas e no tempo presente imperativo.

---

## 1. Estrutura Canônica da Mensagem

```
<tipo>(<escopo opcional>): <descrição curta no imperativo>

[corpo opcional explicando o 'porquê' e detalhes técnicos]

[rodapé opcional com Breaking Changes ou referências a issues]
```

### Exemplo:
```git
feat(auth): add OAuth2 refresh token rotation mechanism

Implement automatic refresh token revocation when reused to prevent replay attacks.
Tokens are stored encrypted in Redis with 7-day TTL.

Closes #142
BREAKING CHANGE: The /auth/refresh endpoint now requires device_id in request payload.
```

---

## 2. Tipos Semânticos Permitidos

| Tipo | Quando Usar | Impacto SemVer |
|---|---|---|
| `feat` | Nova funcionalidade para o usuário ou API | **MINOR** (0.X.0) |
| `fix` | Correção de bug em produção ou funcionalidade | **PATCH** (0.0.X) |
| `refactor` | Mudança de código que não altera comportamento nem corrige bug | **PATCH** (0.0.X) |
| `perf` | Melhoria de desempenho ou otimização de consultas/processamento | **PATCH** (0.0.X) |
| `docs` | Alterações exclusivamente em documentação ou README | Nenhum |
| `style` | Formatação de código, ponto e vírgula, espaços (sem alteração lógica) | Nenhum |
| `test` | Adição, correção ou refatoração de testes automatizados | Nenhum |
| `chore` | Manutenção de dependências, tarefas de build ou configs auxiliares | Nenhum |
| `ci` | Alterações em pipelines de CI/CD (GitHub Actions, workflows) | Nenhum |

---

## 3. Regras de Ouro de Redação

1. **Descrição curta:**
   - Use o tempo presente imperativo: *"add feature"* (e NÃO *"added feature"* ou *"adds feature"*).
   - Inicie em letra minúscula logo após os dois pontos.
   - NÃO finalize a primeira linha com ponto final (`.`).
   - Máximo de 72 caracteres no cabeçalho.
2. **Breaking Changes:**
   - Adicione um ponto de exclamação `!` antes dos dois pontos no tipo/escopo:
     `feat(api)!: remove deprecated v1 user endpoint`
   - OU declare `BREAKING CHANGE: <descrição>` no rodapé da mensagem.

---

## 4. O que NUNCA fazer

* ❌ `git commit -m "ajustes"` ou `git commit -m "fixes"` (Mensagens genéricas).
* ❌ `git commit -m "WIP"` ou `git commit -m "testando"`.
* ❌ Misturar múltiplos assuntos não relacionados no mesmo commit (faça commits atômicos).
