---
name: auth-jwt-helper
description: Utilitário para validação e geração de tokens JWT seguros no backend com HMAC-SHA256 e expiração configurável.
tags: [auth, jwt, security, backend]
globs: ["src/auth/**/*.py", "app/security.py"]
compatible_with: [claude, gemini, cursor, windsurf, copilot, antigravity]
status: draft
version: "1.0.0"
---

# Auth JWT Helper

> [!IMPORTANT]
> Nunca armazene segredos do JWT (`SECRET_KEY`) no código fonte. Utilize sempre variáveis de ambiente.

## Quando usar
- Implementação de autenticação stateless em APIs REST.
- Validação de access tokens e refresh tokens em endpoints protegidos.

## Como fazer
1. Carregue `JWT_SECRET_KEY` e `JWT_ALGORITHM` via configurações centralizadas.
2. Defina TTL curto para access tokens (ex: 15 a 60 minutos).
