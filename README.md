# skills-library — fonte da verdade

Este diretório é o repositório canônico de Skills (`https://github.com/sandrofreitas-web/skills-library.git`),
independente de qualquer projeto específico. Todos os projetos apontam para
ele (via git submodule, subtree ou clone compartilhado — veja `scripts/sync_skills.py`).

## Estrutura

```
skills-library/
├── .github/
│   └── workflows/
│       └── validate.yml      # CI: validação automática do catálogo e sintaxe
├── global/
│   ├── interface-design/SKILL.md (+ agents/)
│   ├── code-review/SKILL.md
│   ├── writing-pt-br/SKILL.md
│   ├── managing-python-dependencies/SKILL.md
│   ├── docker-best-practices/SKILL.md
│   ├── git-conventional-commits/SKILL.md
│   ├── fastapi-clean-architecture/SKILL.md
│   ├── auth-jwt-helper/SKILL.md
│   └── skill-creator/SKILL.md (+ scripts/, references/ e evals)
├── templates/
│   └── SKILL_TEMPLATE.md
├── scripts/
│   └── sync_skills.py
└── catalog.json
```

## Critério: Global ou Local?

Toda skill nasce **local**, dentro do projeto onde o problema apareceu.
Promova para `global/` só quando pelo menos um destes critérios for verdadeiro:

| Sinal | Local | Global |
|---|---|---|
| Reuso | usada em 1 projeto | usada (ou claramente útil) em ≥2 projetos |
| Conteúdo | referencia paths, nomes de tabela, credenciais específicas do projeto | generalizável, sem hardcode |
| Estabilidade | ainda mudando com frequência | já estabilizou |
| Natureza | regra de negócio de 1 cliente/produto | prática técnica/metodológica geral |

Regra prática: **comece local, promova quando copiar e colar pela segunda vez.**

## O catálogo (`catalog.json`)

Antes de criar qualquer skill nova — local ou global — busque no
`catalog.json`. Ele existe justamente para responder "isso já existe em algum
lugar?" sem precisar vasculhar pastas manualmente. Cada entrada tem:

- `description`: quando usar (mesmo texto do frontmatter do SKILL.md)
- `tags`: para busca
- `compatible_with`: quais LLMs/ferramentas ela já foi testada
- `used_by`: quais projetos consomem essa skill
- `status`: `draft` | `stable` | `deprecated`
- `version`: semver simples

Ao pedir para uma LLM criar uma skill nova, a instrução padrão deve ser:
*"Consulte `catalog.json` antes de escrever do zero. Se existir algo
parecido, estenda/adapte em vez de duplicar."*

## Ciclo de vida

1. Nasce local → resolve um problema pontual.
2. Detecta duplicação em outro projeto → candidata a promoção.
3. Promove: generaliza, documenta, versiona, registra no catálogo.
4. Projetos passam a **referenciar** a skill global (via `skills.lock.json` +
   `sync_skills.py`), nunca copiam manualmente.
5. Skill obsoleta vira `status: deprecated` no catálogo (não é apagada, para
   manter histórico e não quebrar quem ainda referencia a versão antiga).

## Pastas nativas de cada LLM — o que o sync gera e por quê

O `SKILL.md` é o formato canônico (portável). O script de sync converte esse
canônico para o formato que cada ferramenta realmente lê em disco. Você nunca
escreve direto nessas pastas — elas são "build output".

### `.claude/` — Claude Code / Claude.ai (via projeto)
```
.claude/
└── skills/
    └── <nome-da-skill>/
        └── SKILL.md      # frontmatter (name, description) + corpo
```
Formato nativo — é o mesmo `SKILL.md`, só copiado (ou linkado). Claude Code
também lê skills pessoais em `~/.claude/skills/` (escopo do usuário, fora de
qualquer projeto — útil para preferências suas que valem em tudo que você
roda localmente, independente do projeto).

### `.gemini/` — Gemini CLI
```
.gemini/
├── GEMINI.md              # arquivo raiz, importa os demais
└── skills/
    └── <nome-da-skill>.md
```
Gemini CLI não tem conceito nativo de "skill" — ele carrega arquivos
`GEMINI.md` hierarquicamente (`~/.gemini/GEMINI.md` global do usuário →
`GEMINI.md` na raiz do projeto → subpastas). O sync gera um `GEMINI.md` que
importa cada skill via `@skills/<nome>.md`, simulando o carregamento modular.
Diferença importante: Gemini CLI concatena **tudo** no contexto (não tem
progressive disclosure real) — por isso o sync só inclui aqui as skills
marcadas como `compatible_with: ["gemini"]` no catálogo, para não estourar
contexto com skills irrelevantes.

### `.cursor/rules/` — Cursor
```
.cursor/
└── rules/
    └── <nome-da-skill>.mdc   # frontmatter: description, globs, alwaysApply
```
Cursor exige extensão `.mdc` com frontmatter próprio (não é o mesmo YAML do
Claude). O sync traduz `description` do SKILL.md para o campo `description`
do `.mdc`, e por padrão gera `alwaysApply: false` (a regra só carrega quando
relevante, igual ao comportamento de skill do Claude).

### `.windsurf/rules/` — Windsurf
```
.windsurf/
└── rules/
    └── <nome-da-skill>.md
```
Mesmo princípio do Cursor, formato mais simples (markdown puro, sem `.mdc`).

### `.github/copilot-instructions.md` — GitHub Copilot
```
.github/
└── copilot-instructions.md   # arquivo único, concatenado
```
Copilot não suporta múltiplos arquivos nem carregamento sob demanda — tudo
que ele lê é esse arquivo único. O sync concatena as skills compatíveis em
seções (`## <nome-da-skill>`), então **evite** colocar skills muito longas
aqui; prefira as mais enxutas ou um resumo com link para o SKILL.md completo.

### `AGENTS.md` (opcional, "ponte" entre ferramentas)
Várias ferramentas mais novas (incluindo modo `AGENTS.md` do Cursor) já leem
um `AGENTS.md` simples na raiz como alternativa às pastas específicas. Se seu
objetivo é máxima portabilidade com o mínimo de manutenção, o sync também
pode gerar um `AGENTS.md` consolidado — trate-o como fallback genérico, não
substituto das pastas nativas quando a ferramenta suporta algo mais rico
(como progressive disclosure do Claude).

## Resumo — tabela de mapeamento

| Ferramenta | Pasta nativa | Escopo usuário (todos os projetos) | Escopo projeto |
|---|---|---|---|
| Claude Code | `.claude/skills/<nome>/SKILL.md` | `~/.claude/skills/` | `<projeto>/.claude/skills/` |
| Gemini CLI | `.gemini/GEMINI.md` (+ imports) | `~/.gemini/GEMINI.md` | `<projeto>/.gemini/GEMINI.md` |
| Cursor | `.cursor/rules/*.mdc` | Settings → Rules for AI | `<projeto>/.cursor/rules/` |
| Windsurf | `.windsurf/rules/*.md` | Settings → Global rules | `<projeto>/.windsurf/rules/` |
| GitHub Copilot | `.github/copilot-instructions.md` | — (não tem escopo global) | `<projeto>/.github/copilot-instructions.md` |
| Genérico/fallback | `AGENTS.md` | — | raiz do projeto |

---

### 4. Executar o Dashboard Web (Skills OS — Antigravity Edition)
Para gerenciar visualmente o catálogo, frota de projetos e transpilar skills em tempo real:
```bash
uv run python skills-library/ui/app.py
# ou (dentro da pasta ui):
python app.py
```
> Acesse no navegador: `http://localhost:4100`

---

## 🖥️ Skills OS — Antigravity IDE Dashboard

O dashboard web inclui:
- **Hub Global com Split Inspector:** Busca dinâmica, inspeção side-by-side com visualização de metadados, código canônico `SKILL.md` e ação de edição instantânea.
- **Frota de Projetos (Fleet Manager):** Monitoramento de repositórios conectados, validação das pastas compiladas (`.cursor`, `.claude`, `.gemini`, etc.), ativação seletiva de skills no `skills.lock.json` e sincronização em massa ou individual.
- **Skill Studio & Live Preview:** Editor com visual sistêmico Antigravity IDE (fontes monoespaçadas balanceadas), validação de YAML frontmatter e preview compilado simultâneo para Cursor, Claude, Gemini, Windsurf e Copilot, com botão **`💾 Salvar / Publicar Skill`** integrado ao `catalog.json`.
- **Console / Terminal Integrado:** Registro de compilação em tempo real e linter de CI integrado.


