# Documentação do Axion Cockpit

Bem-vindo ao centro de documentação do **Axion Cockpit**, o console local de observabilidade arquitetural e gestão operacional da frota de projetos.

---

## Mapa da Documentação

```mermaid
flowchart TD
    Index["docs/README.md\n(Você está aqui)"]
    Arch["docs/ARCHITECTURE.md\n(Arquitetura, Fluxos e Techspec)"]
    Api["docs/API.md\n(Especificação da REST API)"]
    DockerDoc["docs/DOCKER.md\n(Operação com Docker e Compose)"]
    DevDoc["docs/DEVELOPMENT.md\n(Guia do Desenvolvedor & Testes)"]
    DesignAppr["docs/designs/local_project_os.md\n(Design Técnico Project OS)"]
    DesignInfra["docs/designs/infra_and_subsystems_catalog.md\n(Design Técnico Infra & Portas)"]
    ReviewsHub["docs/reviews/README.md\n(Histórico de Auditorias EGM Swarm)"]

    Index --> Arch
    Index --> Api
    Index --> DockerDoc
    Index --> DevDoc
    Index --> DesignAppr
    Index --> DesignInfra
    Index --> ReviewsHub
```

---

## Seções Principais

### 1. [Arquitetura & Especificação](file:///C:/Docker/axion-cockpit/docs/ARCHITECTURE.md)
* Princípios de design (Observador Passivo, Zero-Drift, Zero-Dependencies).
* Diagramas de componentes e fluxogramas operacionais em Mermaid.js.
* Modelo de persistência em arquivos planos (`projects.json`, `config.json` e Markdown).
* Especificação técnica do sistema.

### 2. [Referência da REST API](file:///C:/Docker/axion-cockpit/docs/API.md)
* Documentação de todos os endpoints REST (`/api/projects`, `/api/projects/{id}/docs`, `/api/projects/{id}/notes`, `/api/infra`, `/api/infra/config`).
* Exemplos de requisições, payloads JSON e códigos de resposta HTTP.

### 3. [Guia de Docker & Contêineres](file:///C:/Docker/axion-cockpit/docs/DOCKER.md)
* Inicialização rápida via `docker compose up -d`.
* Mapeamento de volumes para inspeção de repositórios locais do host e cofre do Obsidian.
* Configuração de variáveis de ambiente (`HOST`, `PORT`, `AXION_VAULT_HOST_DIR`).
* Verificação de integridade e Healthcheck.

### 4. [Guia de Desenvolvimento & Testes](file:///C:/Docker/axion-cockpit/docs/DEVELOPMENT.md)
* Configuração de ambiente local (Python Stdlib e `uv`).
* Como executar e estender a suíte de testes automatizados (`test_server.py`, `test_infra_scanner.py`).
* Boas práticas de contribuição e convenções de código.

### 5. [Designs Técnicos Formais](file:///C:/Docker/axion-cockpit/docs/designs/)
* [docs/designs/local_project_os.md](file:///C:/Docker/axion-cockpit/docs/designs/local_project_os.md): Especificação arquitetural do console de projetos e ledger de notas desacoplado.
* [docs/designs/infra_and_subsystems_catalog.md](file:///C:/Docker/axion-cockpit/docs/designs/infra_and_subsystems_catalog.md): Especificação técnica do catálogo passivo de infraestrutura global e radar de colisão de portas.

### 6. [Histórico de Auditorias e Revisões (EGM Swarm)](file:///C:/Docker/axion-cockpit/docs/reviews/README.md)
* Registro completo das deliberações das lentes de arquitetura (`egm-zoom-out`, `egm-comprehension`, `egm-design`, `egm-implementation-readiness`, `egm-synthesizer`).
