# Referência da REST API — Axion Cockpit

A API REST do **Axion Cockpit** é fornecida nativamente pelo módulo [ui/app.py](file:///C:/Docker/axion-cockpit/ui/app.py). Todas as respostas são retornadas no formato `application/json` codificado em UTF-8.

---

## Sumário de Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/projects` | Lista todos os projetos cadastrados na frota. |
| `POST` | `/api/projects` | Registra um novo projeto no catálogo. |
| `DELETE` | `/api/projects/{id}` | Remove um projeto do catálogo (não apaga os arquivos do disco). |
| `GET` | `/api/projects/{id}/docs` | Executa scan on-demand dos documentos Markdown e telemetria Git. |
| `POST` | `/api/projects/{id}/version` | Atualiza a versão canônica do projeto. |
| `GET` | `/api/projects/{id}/notes` | Lista todas as anotações e melhorias do projeto. |
| `POST` | `/api/projects/{id}/notes` | Cria ou atualiza uma anotação em arquivo Markdown. |
| `DELETE` | `/api/projects/{id}/notes/{note_id}` | Exclui permanentemente uma anotação de melhoria. |

---

## 1. Gestão da Frota de Projetos

### 1.1. `GET /api/projects`
Retorna a lista completa de projetos registrados no arquivo `data/projects.json`.

**Exemplo de Resposta (200 OK):**
```json
[
  {
    "id": "meu-projeto",
    "name": "Meu Projeto de Exemplo",
    "path": "/mnt/c/Projetos/meu-projeto",
    "current_version": "v1.0.0",
    "created_at": "2026-10-31T07:00:00.000000+00:00",
    "tags": ["python", "backend"]
  }
]
```

### 1.2. `POST /api/projects`
Cadastra um novo diretório de projeto. O caminho deve existir fisicamente e ser acessível.

**Corpo da Requisição (JSON):**
```json
{
  "name": "E-Commerce Microservice",
  "path": "/mnt/c/Docker/ecommerce-ms",
  "current_version": "v0.9.0",
  "tags": ["nodejs", "prisma", "docker"]
}
```

**Respostas:**
* `201 Created`: Projeto registrado com sucesso.
* `400 Bad Request`: Nome ou caminho ausentes, caminho inválido ou diretório inacessível.
* `409 Conflict`: Já existe um projeto com o ID gerado.

### 1.3. `DELETE /api/projects/{id}`
Remove o projeto do registro central. Os arquivos físicos no disco do host e as notas associadas não são deletados.

**Respostas:**
* `200 OK`: `{"status": "deleted", "id": "meu-projeto"}`
* `404 Not Found`: Projeto não encontrado.

---

## 2. Inspeção On-Demand de Documentação e Git

### 2.1. `GET /api/projects/{id}/docs`
Executa o scanner passivo no diretório configurado, coletando o Markdown principal, blocos Mermaid de fluxogramas e banco de dados, telemetria Git e indicadores de ambiente.

**Exemplo de Resposta (200 OK):**
```json
{
  "project": {
    "id": "meu-projeto",
    "name": "Meu Projeto de Exemplo",
    "path": "/mnt/c/Projetos/meu-projeto",
    "current_version": "v1.0.0"
  },
  "docs": {
    "files_found": [
      {
        "relative_path": "docs/ARCHITECTURE.md",
        "size_bytes": 4820,
        "modified_at": 1793440000.0
      }
    ],
    "primary_doc": "# Arquitetura...",
    "workflows": [
      {
        "type": "flowchart",
        "code": "flowchart TD\n  A --> B",
        "source_file": "docs/ARCHITECTURE.md"
      }
    ],
    "database": [
      {
        "type": "erDiagram",
        "code": "erDiagram\n  USER ||--o{ ORDER : places",
        "source_file": "docs/ARCHITECTURE.md"
      }
    ],
    "git": {
      "is_repo": true,
      "branch": "main",
      "is_dirty": false,
      "uncommitted_count": 0,
      "last_commit": "a1b2c3d - Adiciona testes unitários (2 hours ago)"
    },
    "env_indicators": {
      "has_pyproject": false,
      "has_package_json": true,
      "has_dockerfile": true,
      "has_compose": true,
      "has_prisma": false
    }
  }
}
```

---

## 3. Gestão de Versão Canônica

### 3.1. `POST /api/projects/{id}/version`
Atualiza a versão canônica do projeto registrada no catálogo central.

**Corpo da Requisição (JSON):**
```json
{
  "version": "v1.1.0"
}
```

**Respostas:**
* `200 OK`: `{"status": "updated", "id": "meu-projeto", "current_version": "v1.1.0"}`
* `400 Bad Request`: Versão vazia ou inválida.
* `404 Not Found`: Projeto não encontrado.

---

## 4. Ledger de Anotações e Melhorias (Markdown)

### 4.1. `GET /api/projects/{id}/notes`
Retorna todas as notas salvas no subdiretório `data/notes/{project_id}/`.

**Exemplo de Resposta (200 OK):**
```json
[
  {
    "id": "20261031_071000_exportacao-svg",
    "title": "Exportação SVG de Diagramas Mermaid",
    "status": "planned",
    "version_target": "v1.1.0",
    "created_at": "2026-10-31T07:10:00+00:00",
    "target_files": ["ui/static/app.js", "ui/index.html"],
    "body": "### Especificação\nAdicionar botão de exportar diagrama diretamente como arquivo SVG vetorial."
  }
]
```

### 4.2. `POST /api/projects/{id}/notes`
Cria uma nova anotação ou substitui uma existente. As notas são armazenadas no disco com frontmatter YAML leve e corpo Markdown legível.

**Corpo da Requisição (JSON):**
```json
{
  "id": "20261031_071000_exportacao-svg",
  "title": "Exportação SVG de Diagramas Mermaid",
  "status": "in_review",
  "version_target": "v1.1.0",
  "target_files": ["ui/static/app.js"],
  "body": "Validação em andamento dos nós interativos."
}
```

### 4.3. `DELETE /api/projects/{id}/notes/{note_id}`
Remove permanentemente o arquivo `.md` correspondente à nota em `data/notes/{project_id}/`.

**Respostas:**
* `200 OK`: `{"status": "deleted", "id": "20261031_071000_exportacao-svg"}`
* `404 Not Found`: Nota não encontrada.
