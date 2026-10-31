# ==============================================================================
# Axion Cockpit — Dockerfile
# Imagem enxuta baseada em Python 3.12 Slim (Zero dependências externas de pip)
# ==============================================================================

FROM python:3.12-slim AS runner

# Metadados
LABEL maintainer="Sandro Freitas"
LABEL description="Axion Cockpit — Console Operacional e Arquitetural de Projetos"

# Configurações de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=4100

# Instala Git (para telemetria de repositórios inspecionados) e curl (diagnóstico/saúde)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Cria estrutura de dados e copia aplicação
COPY ui/ ./ui/
COPY tests/ ./tests/
COPY templates/ ./templates/
COPY docs/ ./docs/
COPY README.md ./README.md

# Garante a existência do diretório data
RUN mkdir -p /app/data/notes

# Se houver data local durante o build, copia; caso contrário, app.py inicializa vazio
COPY data/ ./data/

# Volume persistente para catálogo de projetos e anotações
VOLUME ["/app/data"]

# Expõe a porta padrão do Axion Cockpit
EXPOSE 4100

# Healthcheck nativo consultando o endpoint da REST API
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4100/api/projects').read()" || exit 1

# Comando de inicialização
CMD ["python", "ui/app.py"]
