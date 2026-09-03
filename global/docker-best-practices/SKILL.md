---
name: docker-best-practices
description: >
  Diretrizes de engenharia para Docker e Docker Compose: Dockerfile multi-stage builds,
  otimização de cache de camadas, usuário non-root para segurança, healthchecks,
  .dockerignore e configurações de rede/volumes em ambientes de desenvolvimento e produção.
tags: [docker, devops, containers, compose, security, multi-stage]
globs: ["Dockerfile*", "docker-compose*.yml", "compose.yml", ".dockerignore"]
compatible_with: [claude, gemini, cursor, windsurf, copilot, antigravity]
status: stable
version: "1.0.0"
---

# Docker & Containerization Best Practices

> [!IMPORTANT]
> Containers devem ser reproduzíveis, seguros, leves e eficientes em cache de build. Nunca execute containers como `root` em produção e sempre utilize `.dockerignore`.

---

## 1. Regras Fundamentais para Dockerfile

### 1.1 Multi-Stage Builds (Obrigatório para Produção)
Separe a etapa de build (compiladores, SDKs, devDependencies) da imagem final de execução (apenas runtime e binários necessários).

```dockerfile
# --- Stage 1: Build & Dependencies ---
FROM python:3.13-slim AS builder
WORKDIR /app

# Instala ferramentas com cache eficiente
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Stage 2: Runtime Final ---
FROM python:3.13-slim AS runner
WORKDIR /app

# Cria usuário não-privilegiado (Segurança)
RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/false appuser

# Copia venv do builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copia apenas o código fonte
COPY --chown=appuser:appgroup ./src ./src

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2. Otimização de Cache de Camadas (Layer Caching)

1. **Ordem de Cópias:** Copie primeiro arquivos de manifesto de dependências (`package.json`, `pnpm-lock.yaml`, `pyproject.toml`, `uv.lock`) e instale dependências **antes** de copiar o código fonte.
2. **Encadeamento de Comandos:** Agrupe comandos `apt-get` ou `apk` em uma única instrução `RUN` e limpe o cache de pacotes no mesmo passo:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
       && rm -rf /var/lib/apt/lists/*
   ```

---

## 3. Segurança & Boas Práticas

* **Nunca usar tag `latest` em produção:** Especifique versões explícitas de imagem base (ex: `node:20.12-alpine3.19`, `python:3.13-slim`).
* **Usuário Não-Root:** Declare `USER <username>` antes de expor portas ou definir o `CMD`.
* **Segredos e Credenciais:** Nunca faça `COPY .env` ou passe tokens via `ARG` que persistam em camadas. Utilize Docker BuildKit Secret Mounts:
  ```dockerfile
  # syntax=docker/dockerfile:1.4
  RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret ...
  ```

---

## 4. `.dockerignore` Essencial

Todo projeto Docker DEVE conter um `.dockerignore` na raiz contendo no mínimo:
```
.git
.gitignore
.venv
__pycache__/
*.py[cod]
node_modules/
.env*
.DS_Store
dist/
build/
coverage/
*.log
```

---

## 5. Docker Compose para Desenvolvimento & Produção

* Utilize `compose.override.yml` para configurações locais (hot-reload, portas expostas, volumes de código).
* Utilize variáveis de ambiente parametrizadas via `${ENV_VAR:-default_val}`.
* Defina limites de recursos (`mem_limit`, `cpus`) em serviços críticos (bancos, Redis).
