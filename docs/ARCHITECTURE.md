# Arquitetura — Axion Cockpit

O **Axion Cockpit** é um console local de observabilidade e gestão operacional para desenvolvedores e arquitetos que gerenciam múltiplos projetos distribuídos no sistema de arquivos.

Este documento formaliza a arquitetura do sistema, seus fluxos de trabalho e seus modelos de persistência desacoplada.

---

## 1. Princípios Arquiteturais

1. **Princípio do Observador Passivo**:
   - O Axion Cockpit não altera o código dos projetos monitorados nem força padrões invasivos.
   - Não requer agentes nem orquestração ativa rodando dentro dos projetos da frota.
2. **Zero Drift (Leitura On-Demand)**:
   - Toda inspeção de documentação é lida sob demanda diretamente do disco em tempo real (<1ms em SSDs locais).
   - Não são mantidos caches redundantes de especificações técnicas ou diagramas.
3. **Zero Dependências Externas (Python Stdlib)**:
   - O backend opera 100% sobre a biblioteca padrão do Python (`http.server`, `socketserver`, `pathlib`, `re`, `subprocess`).
   - Não necessita de gerenciadores de pacotes (`pip`), frameworks pesados (`FastAPI`, `Django`) ou compiladores de runtime no host.
4. **Renderização Client-Side**:
   - O processamento visual de diagramas (`flowchart`, `sequenceDiagram`, `erDiagram`) é executado no navegador do usuário via **Mermaid.js**, com controles dinâmicos de zoom, pan e tela cheia.
5. **Ledger de Ideias e Débitos Desacoplado**:
   - Anotações de melhoria e débitos técnicos são salvos em arquivos Markdown com frontmatter YAML leve no diretório do console (`data/notes/{project_id}/`), mantendo o repositório monitorado limpo até a formalização de novas versões.

---

## 2. Visão Geral dos Componentes

```mermaid
flowchart TD
    subgraph Host ["Ambiente do Usuário / Host OS"]
        TerminalCLI["Terminal / Agente CLI (ex: Orca)"]
        ProjectsDir["Projetos em Disco (Git Repos, docs, código, compose)"]
        VaultDir["Knowledge Vault (02_Recursos_e_Infra/*.md)"]
    end

    subgraph Axion_Container ["Axion Cockpit (Container Docker / Processo Local)"]
        subgraph WebClient ["Dashboard Web (Porta 4100)"]
            TopbarDomains["Alternador de Domínio (Projetos / Infra)"]
            SPA["SPA Dark Cockpit (HTML5 / Vanilla JS)"]
            MermaidEngine["Engine Mermaid.js (Client-side Zoom/Pan)"]
            KanbanNotes["Quadro de Notas & Versão"]
            InfraDeck["Deck de Hosts & Radar de Portas"]
        end

        subgraph CoreBackend ["Backend (ui/app.py)"]
            RESTServer["HTTP REST Server (http.server)"]
            ScannerEngine["Motor de Scanner Passivo (ui/scanner.py)"]
            InfraEngine["Scanner de Infra & Subsistemas (ui/infra_scanner.py)"]
            GitTelemetry["Telemetria Git (subprocess 'git')"]
            SecurityGuard["Guarda de Caminhos (Anti-Path Traversal)"]
        end

        subgraph Storage ["Persistência Local (data/)"]
            ProjectsDB[("projects.json")]
            ConfigDB[("config.json")]
            NotesStorage[("notes/{project_id}/*.md")]
        end
    end

    TerminalCLI -.->|"Implementa alterações"| ProjectsDir
    ProjectsDir <---|Leitura passiva on-demand| ScannerEngine
    ProjectsDir <---|Portas docker-compose| InfraEngine
    VaultDir <---|Fichas declarativas Markdown/YAML| InfraEngine
    ProjectsDir <---|Status e branches| GitTelemetry
    SPA <-->|"HTTP / JSON REST API"| RESTServer
    RESTServer --> ScannerEngine
    RESTServer --> InfraEngine
    RESTServer --> GitTelemetry
    RESTServer --> SecurityGuard
    RESTServer <--> ProjectsDB
    RESTServer <--> ConfigDB
    RESTServer <--> NotesStorage
```

---

## 3. Fluxo de Inspeção e Telemetria

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Desenvolvedor / Operador
    participant UI as Dashboard Web (SPA)
    participant API as Axion Cockpit API (app.py)
    participant Scan as Scanner Passivo (scanner.py)
    participant Disk as Sistema de Arquivos Local (Projeto)

    Dev->>UI: Clica em um Projeto cadastrado
    UI->>API: GET /api/projects/{id}/docs
    API->>Scan: scan_project_docs(project_path)
    Scan->>Disk: Verifica existência e permissão de caminho
    Scan->>Disk: Lê ARCHITECTURE.md, TECHSPEC.md, README.md (<2MB)
    Scan->>Disk: Executa 'git -C <path> branch --show-current'
    Scan->>Disk: Executa 'git -C <path> status --porcelain'
    Scan->>Disk: Executa 'git -C <path> log -1'
    Scan-->>API: Consolida texto bruto, blocos Mermaid e telemetria Git
    API-->>UI: Retorna JSON consolidado (200 OK)
    UI->>UI: Interpreta Markdown e renderiza blocos Mermaid
    UI-->>Dev: Exibe Techspecs, Diagramas Interativos e Status Git
```

---

## 4. Modelo de Entidades e Persistência

A persistência do Axion Cockpit é intencionalmente baseada em arquivos planos (`JSON` e `Markdown`), eliminando a necessidade de bancos relacionais ou motores de migração:

```mermaid
erDiagram
    PROJECT ||--o{ NOTE : contains
    PROJECT {
        string id PK "Identificador único slug"
        string name "Nome legível do projeto"
        string path "Caminho absoluto no disco local"
        string current_version "Versão canônica atual (ex: v1.0.0)"
        string created_at "Data ISO de cadastro"
        string[] tags "Categorias e tecnologias"
    }
    NOTE {
        string id PK "Timestamp + slug (ex: 20261031_071000_titulo)"
        string title "Título da anotação de melhoria"
        string status "Status: idea | planned | in_review | incorporated"
        string version_target "Versão alvo prevista (ex: v1.1.0)"
        string created_at "Data ISO de criação"
        string[] target_files "Arquivos candidatos a modificação"
        string body "Corpo explicativo em Markdown"
    }
```

---

## 5. Especificação Técnica (Techspec)

| Propriedade | Especificação |
|---|---|
| **Runtime Backend** | Python 3.10+ (Standard Library) |
| **Dependências pip** | Zero (`pip install` desnecessário) |
| **Porta Padrão** | `4100` (TCP) |
| **Host Bind** | `127.0.0.1` (local) ou `0.0.0.0` (Docker) |
| **Frontend** | Vanilla JavaScript (ES6+), CSS Grid/Flexbox moderno, Mermaid.js v10 via CDN |
| **Arquivos de Dados** | `data/projects.json` e `data/notes/{project_id}/*.md` |
| **Formatos Reconhecidos** | `ARCHITECTURE.md`, `TECHSPEC.md`, `WORKFLOWS.md`, `DATABASE.md`, `README.md` |
