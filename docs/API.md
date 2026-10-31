# Referência da REST API — Axion Cockpit

A API REST do **Axion Cockpit** é fornecida nativamente pelo módulo [ui/app.py](file:///C:/Docker/axion-cockpit/ui/app.py). Todas as respostas são retornadas no formato `application/json` codificado em UTF-8.

---

## Sumário de Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/projects` | Lista todos os projetos cadastrados na frota. |
| `POST` | `/api/projects` | Registra um novo projeto no catálogo via caminho em disco. |
| `POST` | `/api/projects/ingest` | Ingestão de projetos via seletor de pastas com arquivos documentais. |
| `GET` | `/api/projects/discover` | Descobre automaticamente diretórios de projetos no ambiente/volume. |
| `GET` | `/api/system/browse` | Navegador de pastas do sistema de arquivos para exploração interativa. |
| `DELETE` | `/api/projects/{id}` | Remove um projeto do catálogo (não apaga os arquivos do disco). |
| `GET` | `/api/projects/{id}/docs` | Executa scan on-demand dos documentos Markdown e telemetria Git. |
| `GET` | `/api/projects/{id}/git-telemetry` | Coleta dados e status em tempo real do Git. |
| `POST` | `/api/projects/{id}/version` | Atualiza a versão canônica do projeto. |
| `GET` | `/api/projects/{id}/notes` | Lista todas as anotações e melhorias do projeto. |
| `POST` | `/api/projects/{id}/notes` | Cria uma anotação em arquivo Markdown. |
| `PUT` | `/api/projects/{id}/notes/{note_id}` | Atualiza uma anotação de melhoria existente. |
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
    "path": "C:\\Docker\\meu-projeto",
    "resolved_path": "/projects/meu-projeto",
    "current_version": "v1.0.0",
    "created_at": "2026-10-31T07:00:00.000000+00:00",
    "tags": ["python", "backend"],
    "accessible": true,
    "git": {
      "is_repo": true,
      "branch": "main",
      "is_dirty": false,
      "uncommitted_count": 0
    },
    "env": {
      "has_dockerfile": true,
      "has_compose": true
    }
  }
]
```

### 1.2. `POST /api/projects`
Cadastra um novo diretório de projeto. O caminho pode ser no formato Windows (ex: `C:\Docker\meu-projeto` com ou sem aspas), caminho do container (`/projects/meu-projeto`) ou relativo.

**Corpo da Requisição (JSON):**
```json
{
  "name": "E-Commerce Microservice",
  "path": "C:\\Docker\\ecommerce-ms",
  "current_version": "v0.9.0",
  "tags": ["nodejs", "prisma", "docker"]
}
```

### 1.3. `POST /api/projects/ingest`
Ingestão de projetos independente do ponto de montagem Docker (suporta pastas em qualquer drive do Windows, como Google Drive `G:\`, rede ou pastas locais).

**Corpo da Requisição (JSON):**
```json
{
  "name": "Personal Finance Cockpit",
  "folder_name": "Finaceiro_pessoal",
  "path": "G:\\Meu Drive\\01 Projetos\\Finaceiro_pessoal",
  "version": "v2.0.1",
  "tags": ["finance", "fastapi", "react"],
  "docs": {
    "README.md": "# Personal Finance Cockpit...",
    "docs/TECSPEC.md": "# Especificação Técnica..."
  },
  "manifests": {
    "has_dockerfile": true,
    "has_compose": true
  }
}
```

### 1.4. `GET /api/projects/discover`
Varre o ambiente e retorna atalhos de projetos detectados no volume montado (`/projects`) ou diretórios vizinhos.

### 1.5. `GET /api/system/browse?path={subpath}`
Permite navegação interativa pelas pastas disponíveis com proteção rigorosa contra *path traversal*.

### 1.6. `DELETE /api/projects/{id}`
Remove o projeto do registro central. Os arquivos físicos no disco do host e as notas associadas não são deletados.

**Respostas:**
* `200 OK`: `{"status": "deleted", "id": "meu-projeto"}`
* `404 Not Found`: Projeto não encontrado.

---

## 2. Inspeção On-Demand de Documentação e Git

### 2.1. `GET /api/projects/{id}/docs`
Executa o scanner passivo no diretório configurado ou nos documentos ingeridos, coletando o Markdown principal, blocos Mermaid de fluxogramas e banco de dados, telemetria Git e indicadores de ambiente.

**Exemplo de Resposta (200 OK):**
```json
{
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

---

### 4.2. `POST /api/projects/{id}/notes`
Cria uma nova anotação. As notas são armazenadas no disco com frontmatter YAML leve e corpo Markdown legível.

---

### 4.3. `DELETE /api/projects/{id}/notes/{note_id}`
Remove permanentemente o arquivo `.md` correspondente à nota em `data/notes/{project_id}/`.
