# Guia de Desenvolvimento — Axion Cockpit

Este guia detalha o fluxo de desenvolvimento, arquitetura de código, convenções e procedimentos de teste para manter o **Axion Cockpit**.

---

## 1. Filosofia do Código

1. **Biblioteca Padrão do Python Apenas**:
   - O backend nunca deve depender de bibliotecas externas instaladas via `pip` no modo operacional normal.
   - Qualquer funcionalidade (servidor HTTP, manipulação de arquivos, parsing de JSON, execução de comandos do sistema) deve ser implementada com a biblioteca padrão (`http.server`, `socketserver`, `json`, `pathlib`, `re`, `subprocess`, etc.).
2. **Observabilidade Passiva**:
   - Nunca altere nem crie arquivos dentro dos projetos monitorados pelo console.
   - Toda telemetria deve ser estritamente de leitura.
3. **Persistência Limpa e Desacoplada**:
   - Dados do Axion Cockpit vivem em `data/projects.json` e notas em `data/notes/{project_id}/*.md`.
   - As notas utilizam um parser de frontmatter YAML leve implementado nativamente em [ui/app.py](file:///C:/Docker/axion-cockpit/ui/app.py).

---

## 2. Estrutura do Código-Fonte

```
axion-cockpit/
├── ui/
│   ├── app.py                 # Servidor HTTP nativo (ThreadingTCPServer), roteador REST e CRUD
│   ├── scanner.py             # Scanner passivo de projetos locais, Git e extração Mermaid
│   ├── infra_scanner.py       # Leitor de fichas declarativas no vault e colisão de portas
│   ├── index.html             # Single Page Application (Dark Cockpit)
│   └── static/
│       ├── app.js             # Lógica frontend, radar de portas, chamadas à API e Mermaid
│       └── styles.css         # Estilos visuais e layout responsivo
├── tests/
│   ├── test_server.py         # Testes do servidor HTTP, endpoints REST e scanner de projetos
│   └── test_infra_scanner.py  # Testes do parser YAML, regex de compose e colisões de portas
├── templates/
│   └── convention/            # Modelos recomendados para projetos monitorados
│       ├── ARCHITECTURE.template.md
│       └── NOTE.template.md
└── data/                      # Persistência local (catálogo, config e notas Markdown)
```

---

## 3. Execução em Ambiente Local

### Opção A: Python Nativo (Sem ferramentas extras)
```bash
python ui/app.py
```
Por padrão, o servidor escuta em `http://127.0.0.1:4100`.

Para alterar a porta ou host via argumentos de linha de comando:
```bash
python ui/app.py --port 8080 --host 0.0.0.0
```

Ou através de variáveis de ambiente:
```bash
PORT=8080 HOST=0.0.0.0 python ui/app.py
```

### Opção B: Utilizando `uv` (Recomendado para velocidade)
```bash
uv run python ui/app.py
```

---

## 4. Executando os Testes Automatizados

A suíte de testes utiliza o módulo nativo `unittest` e valida:
- Validação de caminhos e prevenção contra path traversal;
- Proteção de diretórios críticos do sistema operacional (`C:\Windows`, `/etc`, `/root`, etc.);
- Extração precisa de blocos Mermaid (`flowchart`, `erDiagram`, `sequenceDiagram`);
- Coleta de telemetria Git sem falhas em diretórios não-versionados;
- Ciclo completo de leitura e escrita de notas Markdown com frontmatter;
- Parsing determinístico de YAML frontmatter com biblioteca padrão Python;
- Extração de portas de arquivos `docker-compose.yml` (short syntax, IP binding);
- Detecção e agrupamento de colisões de portas na matriz de rede;
- Invalidação e expiração de TTL de cache (30 segundos).

### Com Python nativo:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Com `uv`:
```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

### Com Docker:
```bash
docker compose run --rm axion-cockpit python -m unittest discover -s tests -p "test_*.py"
```

---

## 5. Adicionando Novos Testes

Ao estender o scanner ou a API, adicione novos casos de teste em [tests/test_server.py](file:///C:/Docker/axion-cockpit/tests/test_server.py).
Mantenha o padrão de isolamento utilizando `tempfile.TemporaryDirectory()` para manipulação de arquivos de teste.
