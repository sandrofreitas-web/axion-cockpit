# Axion Cockpit — Console Operacional e Arquitetural de Projetos

O **Axion Cockpit** é um console local de observabilidade e gestão operacional para desenvolvedores e arquitetos que gerenciam múltiplos projetos distribuídos no sistema de arquivos.

Ele opera sob o **Princípio do Observador Passivo**:
- **Zero Dependências Externas**: Executa 100% na biblioteca padrão do Python (`http.server` e `socketserver`). Não exige `pip install`, FastAPI ou virtualenvs.
- **Modelo de Ingestão Simplificado**: Suporta seleção direta de pastas do Windows Explorer pelo navegador ou caminhos do host, com ingestão instantânea de arquivos Markdown e manifestos sem depender de pontos rígidos de montagem.
- **Zero Drift (On-Demand)**: Não duplica dados nem persiste caches de documentação desatualizados. Lê os arquivos técnicos sob demanda diretamente do disco em tempo real.
- **Catálogo Passivo de Infraestrutura & Subsistemas**: Mapeia declarativamente hosts físicos, máquinas virtuais, instâncias cloud e serviços a partir de fichas no Obsidian Vault (`02_Recursos_e_Infra/*.md`).
- **Radar de Conflito de Portas**: Cruza automaticamente portas declaradas nos hosts e mapeamentos de portas em manifestos `docker-compose.yml` dos projetos cadastrados, alertando colisões em tempo real.
- **Renderização Visual Interativa (Mermaid.js)**: Diagramas renderizados em tamanho natural legível, com suporte nativo a Pan (arrastar com o mouse), Zoom contínuo (30% a 350%), roda do mouse (Wheel), ajuste automático e Modo Tela Cheia dedicado.
- **Ledger de Melhorias Desacoplado**: Permite registrar ideias, débitos técnicos e notas de revisão por projeto em arquivos Markdown locais, sem poluir a árvore de commits do repositório monitorado até a homologação da versão.
- **Pronto para Docker**: Disponível como imagem contêinerizada enxuta baseada em `python:3.12-slim` com Docker Compose e suporte nativo a volumes.
- **Fronteira com o Orca**: O Axion Cockpit é estritamente uma interface de visualização e gestão passiva. A orquestração e execução de comandos por agentes de IA é conduzida externamente pelo **Orca** ou pelo operador via terminal CLI.

---

## Como Executar

### Opção 1: Com Docker Compose (Recomendado)

Inicie o contêiner imediatamente com uma única linha:

```bash
docker compose up -d
```

Acesse no navegador: **`http://localhost:4100`**

Para parar o serviço:
```bash
docker compose down
```

> Mais detalhes e mapeamento de diretórios de projetos em [docs/DOCKER.md](file:///C:/Docker/axion-cockpit/docs/DOCKER.md).

---

### Opção 2: Python Local (Sem dependências externas)

Como o servidor utiliza exclusivamente a biblioteca padrão do Python 3, a inicialização é instantânea:

```bash
# Iniciar o servidor local na porta padrão 4100
python ui/app.py

# Ou utilizando uv:
uv run python ui/app.py

# Ou especificando porta e host customizados:
python ui/app.py --port 8080 --host 0.0.0.0
```

Abra o navegador em: **`http://127.0.0.1:4100`**

---

## Estrutura do Repositório

```
axion-cockpit/
├── data/                                  # Persistência em arquivos planos
│   ├── projects.json                      # Registro central da frota de projetos locais
│   ├── config.json                        # Configurações do console (ex: vault_path)
│   ├── vault/                             # Ponto de montagem/cópia do Obsidian Vault
│   ├── ingested/                          # Documentações ingeridas via upload/seletor
│   └── notes/                             # Notas de melhoria individuais por projeto
│       └── {project_id}/                  # Arquivos .md com frontmatter
├── docs/                                  # Documentação técnica organizada
│   ├── README.md                          # Portal e índice central da documentação
│   ├── ARCHITECTURE.md                    # Arquitetura, componentes e fluxos Mermaid
│   ├── API.md                             # Referência completa da REST API
│   ├── DOCKER.md                          # Guia detalhado de Docker e Compose
│   ├── DEVELOPMENT.md                     # Guia de desenvolvimento e testes
│   ├── designs/                           # Documentos formais de design técnico
│   │   ├── local_project_os.md            # Design aprovado do Project OS
│   │   └── infra_and_subsystems_catalog.md# Design aprovado do Catálogo de Infra
│   └── reviews/                           # Trilha histórica de auditorias (EGM Swarm)
│       └── README.md                      # Sumário das revisões multi-lente
├── templates/
│   └── convention/
│       ├── ARCHITECTURE.template.md       # Template de arquitetura, techspec e diagramas
│       └── NOTE.template.md               # Template de nota de melhoria com frontmatter
├── tests/
│   ├── test_server.py                     # Testes do servidor HTTP e scanner de projetos
│   └── test_infra_scanner.py              # Testes do scanner de infra e matriz de portas
├── ui/
│   ├── app.py                             # Servidor HTTP/REST nativo (ThreadingTCPServer)
│   ├── scanner.py                         # Scanner passivo, telemetria Git e extração Mermaid
│   ├── infra_scanner.py                   # Parser YAML stdlib, matriz de portas e leitor de vault
│   ├── index.html                         # Interface SPA do dashboard (Axion Cockpit)
│   └── static/
│       ├── app.js                         # Controladores frontend, radar de portas e Mermaid
│       └── styles.css                     # Design system dark cockpit
├── Dockerfile                             # Build da imagem Docker (python:3.12-slim)
├── docker-compose.yml                     # Orquestração do serviço (axion-cockpit)
└── README.md                              # Este documento
```

---

## Documentação Completa

Para aprofundar-se em cada aspecto do Axion Cockpit, consulte a documentação em [docs/](file:///C:/Docker/axion-cockpit/docs/README.md):

* 📐 **[docs/ARCHITECTURE.md](file:///C:/Docker/axion-cockpit/docs/ARCHITECTURE.md)**: Detalhamento arquitetural, fluxogramas operacionais e modelo relacional em Mermaid.js.
* 🔌 **[docs/API.md](file:///C:/Docker/axion-cockpit/docs/API.md)**: Especificação completa de todos os endpoints REST, formatos de requisição e respostas.
* 🐳 **[docs/DOCKER.md](file:///C:/Docker/axion-cockpit/docs/DOCKER.md)**: Manual de containerização, volumes para projetos do host, variáveis de ambiente e healthcheck.
* 💻 **[docs/DEVELOPMENT.md](file:///C:/Docker/axion-cockpit/docs/DEVELOPMENT.md)**: Guia do desenvolvedor, execução de testes unitários e padrões de código.
* 🎯 **[docs/designs/local_project_os.md](file:///C:/Docker/axion-cockpit/docs/designs/local_project_os.md)**: Documento canônico de design técnico do Project OS.
* 🌐 **[docs/designs/infra_and_subsystems_catalog.md](file:///C:/Docker/axion-cockpit/docs/designs/infra_and_subsystems_catalog.md)**: Documento canônico de design do Catálogo de Infraestrutura e Radar de Portas.
* 📜 **[docs/reviews/README.md](file:///C:/Docker/axion-cockpit/docs/reviews/README.md)**: Trilha histórica de revisões arquiteturais e auditorias do EGM Swarm.

---

## Convenção de Documentação Recomendada

O Axion Cockpit reconhece automaticamente qualquer documentação existente nos projetos monitorados. Para máxima riqueza visual, recomenda-se adicionar um arquivo `ARCHITECTURE.md` (ou `docs/ARCHITECTURE.md`, `TECSPEC.md`, `TECHSPEC.md`) contendo:

1. **Visão Geral & Techspec**: Especificação de runtimes, bancos, portas e variáveis críticas.
2. **Workflows Operacionais**: Blocos de código ````mermaid (diagramas `flowchart` ou `sequenceDiagram`).
3. **Banco de Dados**: Blocos de código ````mermaid (diagramas `erDiagram`).

Templates prontos para cópia estão disponíveis em:
- [templates/convention/ARCHITECTURE.template.md](file:///C:/Docker/axion-cockpit/templates/convention/ARCHITECTURE.template.md)
- [templates/convention/NOTE.template.md](file:///C:/Docker/axion-cockpit/templates/convention/NOTE.template.md)

---

## Ciclo de Vida de Melhorias e Atualização de Versão

1. **Registrar Ideia**: No painel do projeto, clique em `+ Nova Anotação` e registre a melhoria com status `idea` ou `planned`.
2. **Implementar no Código**: O operador ou o agente CLI (Orca) realiza as alterações no código físico do projeto monitorado.
3. **Inspecionar Telemetria Git**: O Axion Cockpit exibe o branch ativo e a quantidade de arquivos modificados via telemetria Git em tempo real.
4. **Homologar Versão**: Altere o status da nota para `incorporated` e clique em `🏷️ Atualizar Versão` para registrar o novo número de release canônico no console.

---

## Testes Automatizados

A suíte de testes unitários cobre validação de caminhos, proteção anti-path traversal, extração de diagramas Mermaid, persistência de notas, descoberta de projetos e resolução de documentação ingerida:

```bash
# Executar localmente com Python:
python -m unittest discover -s tests -p "test_*.py"

# Ou com uv:
uv run python -m unittest discover -s tests -p "test_*.py"

# Ou via Docker:
docker compose run --rm axion-cockpit python -m unittest discover -s tests -p "test_*.py"
```
