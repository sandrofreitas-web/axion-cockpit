# Local Project OS (Desvinculação da Skills Library)

* **Author:** Sandro Freitas
* **Date:** 2026-10-30

## Overview

Reestruturação do repositório para transformar a antiga biblioteca de skills em um Sistema Operacional Local de Projetos (Project OS). O sistema atua como um console de observabilidade arquitetural e gestão operacional da frota de projetos em disco. Ele utiliza análise flexível assistida por LLM para interpretar a documentação de cada projeto e gerar resumos visuais (Techspecs, fluxos de trabalho e diagramas de banco de dados em Mermaid), mantendo um ledger de melhorias e ideias em arquivos planos Markdown. A reconciliação entre o estado visual do OS e o diretório físico do projeto ocorre via análise comparativa antes da homologação de novas versões. Toda a infraestrutura legada de catálogo e sincronização de skills é desvinculada e expurgada deste repositório.

## Analysis

### 1. Ingestão Flexível via LLM vs. Parsers Rígidos (Lente de Compreensão e DevEx)
* **Análise Flexível:** Projetos possuem estruturas heterogêneas (pastas `docs/`, `architecture/`, ou documentações na raiz). A análise assistida por LLM permite interpretar o contexto específico de cada projeto e mapear dinamicamente os componentes arquiteturais, evitando falhas por ausência de um arquivo nominal específico.
* **Saída Padronizada:** A saída da análise para o frontend é normalizada em seções visuais: Techspec estruturada, Workflows operacionais (fluxogramas Mermaid) e Diagramas de Dados (ERD Mermaid).

### 2. Ciclo de Reconciliação (Visual OS vs. Diretório Físico) (Lente de Arquitetura de Sistemas)
* **Gatilho de Auditoria e Comparação:** Ao acionar a incorporação de melhorias ou revisão de versão, o sistema executa uma análise de comparação entre os dados consolidados no Visual OS e os registros do diretório real do projeto.
* **Garantia de Não-Regressão e Rastreabilidade:** Nenhuma versão é atualizada sem antes validar se as mudanças planejadas no OS foram de fato aplicadas aos arquivos do projeto, prevenindo divergência entre a documentação e o código real.

### 3. Persistência em Arquivos Planos (Lente de Implementação e Simplicidade)
* **Zero Dependência de Banco de Dados:** O estado do OS é inteiramente persistido em arquivos planos no diretório `data/`:
  - `data/projects.json`: Cadastro dos projetos (id, nome, caminho em disco, metadados).
  - `data/notes/<project_id>/`: Arquivos Markdown individuais contendo ideias, rascunhos de melhorias e históricos de revisão.
* **Portabilidade e Backup:** Todo o estado pode ser inspecionado diretamente no editor de texto ou versionado em Git sem necessidade de ferramentas de migração de banco de dados.

### 4. Desacoplamento da Infraestrutura de Skills (Lente de Topologia e Código)
* Descarte imediato de: `scripts/sync_skills.py`, `catalog.json`, `templates/SKILL_TEMPLATE.md`, pasta `global/` e rotas legadas no backend `ui/app.py`. As skills passam a ser geridas globalmente pelos ambientes de cada LLM.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  - Registro de projetos apontando para seus respectivos caminhos no sistema de arquivos local.
  - Ingestão flexível de documentação assistida por LLM para extração de Techspec, Workflows e Schemas.
  - Renderização gráfica client-side em Mermaid.js com controles de zoom e navegação.
  - Gestão de anotações e backlog de melhorias em arquivos planos Markdown por projeto.
  - Mecanismo de comparação entre o estado do Visual OS e o diretório do projeto antes do bump de versão.
  - Armazenamento 100% baseado em arquivos planos (`projects.json` e arquivos Markdown).
  - Expurgar totalmente o código legado de catálogo e sincronização de skills.

* **Out-of-Scope Non-Goals:**
  - Injeção de código, hooks ou arquivos intrusivos dentro dos diretórios dos projetos monitorados.
  - Orquestração de comandos ou execução direta de runtime de agentes pelo painel (orquestração externa).
  - Utilização de bancos de dados relacionais ou NoSQL para persistência interna do OS.
  - Manutenção ou hospedagem de repositório central de skills.

## Alternatives Weighed

* **Abordagem 1: Parsers Heurísticos Rígidos por Stack**:
  - *Rejeitada*: Quebra frequente ao lidar com repositórios que não seguem nomes de arquivo exatos.
  - *Decisão*: Ingestão flexível assistida por LLM com saída estruturada padrão.
* **Abordagem 2: Banco de Dados Embutido (SQLite)**:
  - *Rejeitada*: Complexidade desnecessária para leitura de poucos projetos locais e histórico de anotações.
  - *Decisão*: Arquivos planos (`projects.json` e Markdown) para portabilidade direta e edição humana simples.
* **Abordagem 3: Atualização Cega de Versão**:
  - *Rejeitada*: Risco de atualizar a versão no OS sem que as alterações tenham sido incorporadas no repositório de fato.
  - *Decisão*: Análise comparativa explícita entre Visual OS e o diretório físico antes de homologar a versão.

## Key Decisions & Staging for Next Steps

1. **Refatoração da API Backend**:
   - Limpar `ui/app.py` removendo endpoints de sincronização de skills.
   - Criar endpoints para projetos (`GET/POST /api/projects`), leitura/análise de documentação (`GET /api/projects/{id}/docs`) e gestão de notas (`GET/POST /api/projects/{id}/notes`).
2. **Definição da Camada de Análise Flexível**:
   - Definir o prompt/pipeline de extração assistida por LLM para consolidar documentação em estruturas Markdown/Mermaid consumíveis pela UI.
3. **Módulo de Comparação e Auditoria**:
   - Implementar o comparador de estado entre as notas incorporadas no OS e o histórico/arquivos do diretório do projeto.
