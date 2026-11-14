# Documentação do Nexus Cockpit

Bem-vindo à documentação técnica do **Nexus Cockpit**. Este diretório centraliza os guias de arquitetura, contratos de API REST, operação em Docker, práticas de desenvolvimento, especificações de design e relatórios de auditoria arquitetural (`EGM Swarm`).

---

## 📖 Guias Operacionais e Técnicos

| Documento | Descrição |
| :--- | :--- |
| [**ARCHITECTURE.md**](ARCHITECTURE.md) | Arquitetura dos módulos (`app.py`, `scanner.py`, `infra_scanner.py`, `vault_parser.py`, `vault_observer.py`), estratégia de snapshot imutável em memória, segurança loopback/CSRF e projeção fechada `AREAS_SAFE_FIELDS`. |
| [**API.md**](API.md) | Especificação completa dos endpoints HTTP REST (`/api/status`, `/api/projects/*`, `/api/infra/*`, `/api/vault/entities`, `/api/vault/overview`, `/api/vault/reindex`). |
| [**DOCKER.md**](DOCKER.md) | Configuração de containers, mapeamento de volumes read-only (`/projects`, `/drive_projects`, `/main_vault`, `/app/ui`), bind em `127.0.0.1:4100` e diagnóstico de mounts do Google Drive (`G:\`). |
| [**DEVELOPMENT.md**](DEVELOPMENT.md) | Fluxo de trabalho local sem dependências externas (`stdlib`), execução da suíte `unittest` (25 testes) e manutenção da paridade com `vault_schemas.json` e `Test-VaultSchemas.ps1`. |

---

## 📐 Especificações de Design (`docs/designs/`)

| Especificação | Status | Escopo |
| :--- | :---: | :--- |
| [**local_project_os.md**](designs/local_project_os.md) | Implementado | Design fundacional do Local Project OS: scanner passivo de projetos, renderização client-side de diagramas Mermaid e Ledger de Melhorias desacoplado do Git. |
| [**infra_and_subsystems_catalog.md**](designs/infra_and_subsystems_catalog.md) | Implementado | Design do Catálogo Passivo de Infraestrutura (`02_Recursos_e_Infra`), extração estática de portas Docker Compose e Radar de Colisão de Portas. |
| [**vault_observability_and_entity_cockpit.md**](designs/vault_observability_and_entity_cockpit.md) | Implementado | Design da Observabilidade do `main_vault` e Visão Executiva por Entidade, manifesto compartilhado `vault_schemas.json`, snapshot imutável em memória e reconciliação N:1. |

---

## 🔍 Trilha de Auditorias e Revisões (`docs/reviews/`)

- [**reviews/README.md**](reviews/README.md) — Índice geral dos artefatos de concepção e auditoria multi-lente (`EGM Swarm`).
  - [**Ciclo 3 — Observabilidade do Main Vault (`reviews/vault_observability/consolidated_review_report.md`)**](reviews/vault_observability/consolidated_review_report.md)
  - [**Ciclo 1 — Local Project OS (`reviews/consolidated_review_report.md`)**](reviews/consolidated_review_report.md)
