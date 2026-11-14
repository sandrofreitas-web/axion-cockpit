# Nexus Cockpit — Local Project OS, Catálogo de Infraestrutura & Observabilidade do Main Vault

![Status](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.12%20(stdlib)-blue) ![Docker](https://img.shields.io/badge/docker-ready-2496ED)

O **Nexus Cockpit** é um console operacional local e autônomo (Single-Page Application + servidor HTTP concorrente nativo em Python 3.12 sem dependências externas) para gerenciamento da frota de projetos locais, catálogo declarativo de infraestrutura com radar de colisão de portas e observabilidade contínua sobre o cofre de conhecimento (`main_vault`).

---

## 🎯 Visão Geral

Projetado sob a filosofia **Zero-Dependency, Zero Persistent Database (`NG4`) & Zero-Drift**, o Nexus Cockpit opera exclusivamente com a biblioteca padrão do Python (`stdlib`) no backend e Vanilla JavaScript (ES6+) no frontend. O registro operacional reside em arquivos planos (`data/projects.json`, `data/config.json`, `data/notes/`), enquanto a telemetria Git, diagramas Mermaid e a observabilidade de contratos do `main_vault` são processados em memória via cache TTL e snapshots imutáveis.

### Principais Funcionalidades

1. **Projetos Locais (`Projetos Locais`)**
   - Inspeção passiva de repositórios locais (`C:\Docker` montado em `/projects:ro` e `G:\Meu Drive\01 Projetos` montado em `/drive_projects:ro`), além de suporte à ingestão documental de pastas do Windows (`data/ingested/`).
   - Extração sob demanda de especificações técnicas Markdown, diagramas operacionais e de banco de dados (`Mermaid.js` com Pan & Zoom e modo tela cheia), telemetria Git nativa (`branch`, `is_dirty`, `uncommitted_count`, `recent_commits`) e indicadores de ambiente.
   - **Ledger de Melhorias Desacoplado**: Quadro Kanban por projeto (`idea`, `planned`, `in_review`, `incorporated`) persistido em arquivos Markdown em `data/notes/<project_id>/`, mantendo rascunhos fora da árvore Git do projeto até a homologação de versão.

2. **Infraestrutura Global & Matriz de Portas (`Infra & Subsistemas`)**
   - Leitura declarativa das fichas de servidores e ambientes em `02_Recursos_e_Infra` combinada com a extração estática de portas de `docker-compose.yml` e `Dockerfile` da frota local.
   - **Radar de Colisão de Portas**: Identificação proativa de conflitos de portas host entre múltiplos projetos e servidores declarados, com barras de distribuição por tipo de host, sistema operacional e entidade.

3. **Observabilidade do Main Vault & Visão por Entidade (`Vault & Entidades`)**
   - Indexação read-only em memória (`VaultObserver` com snapshot imutável protegido por `threading.Lock`) restrita à allowlist de **4 domínios** do `main_vault` (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`), validada contra o manifesto compartilhado `scripts/harness/vault_schemas.json`.
   - Consolidação executiva por entidade (`Todas`, `Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`) com sub-navegação por domínio, busca instantânea e filtro de divergências.
   - **Reconciliação N:1 e Matriz Binária de Divergências (`project_repo_links`)**:
     - `status_mismatch`: Divergência entre o status no vault (`Ativo` vs `Pausado`/`Concluído`/`Arquivado`) e o status operacional no Cockpit.
     - `missing_workspace`: Repositório local referenciado na nota não encontrado nos mounts locais (`/projects` ou `/drive_projects`).
     - `stale_sync`: Defasagem superior a 7 dias entre `ultima_atualizacao` da nota e a data do último commit Git (ou > 30 dias sem revisão em projetos `Ativo` sem Git).
   - **Projeção Segura (`AREAS_SAFE_FIELDS`)**: Notas de `05_Areas` expõem estritamente 13 campos de metadados de governança (`rel_path`, `domain`, `entity`, `title`, `area`, `doc_type`, `status`, `frontmatter_status`, `links_status`, `validation_errors`, `size_bytes`, `doc_date`, `indexed_at`), jamais trafegando o corpo da nota ou `caminho_drive` na API REST.

---

## 🏗️ Estrutura do Repositório

```text
C:\Docker\nexus-cockpit\
├── data/
│   ├── projects.json          # Catálogo da frota de projetos e vínculos com o vault
│   ├── config.json            # Configuração persistida (ex.: override de vault_path)
│   ├── notes/                 # Ledger de melhorias em Markdown por projeto
│   └── ingested/              # Espelho documental de pastas ingeridas via navegador
├── docs/
│   ├── README.md              # Índice central da documentação
│   ├── ARCHITECTURE.md        # Arquitetura de componentes, concorrência e segurança
│   ├── API.md                 # Referência completa dos endpoints REST HTTP
│   ├── DOCKER.md              # Operação de containers, mounts :ro e healthcheck
│   ├── DEVELOPMENT.md         # Guia de desenvolvimento stdlib, testes e paridade de schemas
│   ├── designs/               # Especificações técnicas aprovadas (EGM)
│   └── reviews/               # Trilha histórica de auditorias EGM Swarm
├── templates/
│   └── convention/            # Templates de ARCHITECTURE.md e notas de melhoria
├── tests/
│   ├── test_vault_pipeline.py # Testes do parser YAML, snapshot, N:1, 05_Areas e CSRF
│   ├── test_infra_scanner.py  # Testes do catálogo de infraestrutura e colisão de portas
│   └── test_server.py         # Testes do scanner de projetos, notas e validação de caminhos
├── ui/
│   ├── app.py                 # Servidor HTTP concorrente (ThreadingTCPServer) e API REST
│   ├── scanner.py             # Scanner de projetos locais, Git, Mermaid e docs
│   ├── infra_scanner.py       # Scanner passivo de infraestrutura e portas Docker Compose
│   ├── vault_parser.py        # Parser zero-dep de YAML frontmatter + validador de schema
│   ├── vault_observer.py      # Observador em memória do main_vault e reconciliador N:1
│   ├── index.html             # Interface SPA v2.0 (Projetos, Infra, Vault & Entidades)
│   └── static/
│       ├── app.js             # Controlador frontend, Pan & Zoom Mermaid e filtros
│       └── styles.css         # Design System Carbon Obsidian & Electric Cobalt
├── Dockerfile                 # Imagem baseada em python:3.12-slim com healthcheck nativo
└── docker-compose.yml         # Orquestração com bind 127.0.0.1:4100 e volumes :ro
```

---

## 🚀 Como Executar

### Opção 1: Via Docker Compose (Recomendado)

```powershell
docker compose up -d --build
```

Acesse em: **[http://127.0.0.1:4100](http://127.0.0.1:4100)** (ou `http://localhost:4100`)

### Opção 2: Execução Direta no Host Windows (Desenvolvimento)

Utilizando `uv` com Python 3.12+:

```powershell
uv run python ui/app.py
```

---

## 🧪 Testes Automatizados

A suíte utiliza `unittest` da biblioteca padrão do Python (25 testes cobrindo scanners, parser YAML estrito/leniente, snapshot do vault, reconciliação N:1, isolamento `05_Areas` e travas anti-CSRF):

```powershell
# No host via uv
uv run python -m unittest discover -s tests -p "test_*.py" -v

# Ou dentro do container Docker
docker compose exec nexus-cockpit python -m unittest discover -s tests -p "test_*.py" -v
```

Validação de contratos diretamente no `main_vault` via PowerShell:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "G:\Meu Drive\main_vault\scripts\harness\Test-VaultSchemas.ps1"
```

---

## 📚 Documentação Técnica

Consulte o índice completo em [`docs/README.md`](docs/README.md):

- [**Arquitetura (`docs/ARCHITECTURE.md`)**](docs/ARCHITECTURE.md)
- [**Referência da API (`docs/API.md`)**](docs/API.md)
- [**Guia Docker (`docs/DOCKER.md`)**](docs/DOCKER.md)
- [**Guia de Desenvolvimento (`docs/DEVELOPMENT.md`)**](docs/DEVELOPMENT.md)
- **Especificações de Design (`docs/designs/`)**:
  - [`docs/designs/local_project_os.md`](docs/designs/local_project_os.md)
  - [`docs/designs/infra_and_subsystems_catalog.md`](docs/designs/infra_and_subsystems_catalog.md)
  - [`docs/designs/vault_observability_and_entity_cockpit.md`](docs/designs/vault_observability_and_entity_cockpit.md)
- **Auditorias Arquiteturais (`docs/reviews/`)**:
  - [`docs/reviews/README.md`](docs/reviews/README.md)
