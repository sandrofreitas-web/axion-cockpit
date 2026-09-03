---
name: fastapi-clean-architecture
description: >
  Diretrizes de arquitetura limpa e desacoplada para APIs FastAPI modernas.
  Padroniza organização em camadas (Routers, Services, Repositories, Schemas Pydantic v2),
  injeção de dependências (Depends), tratamento global de exceções, paginação e configurações centralizadas.
tags: [fastapi, python, clean-architecture, pydantic, backend, api]
globs: ["app/**/*.py", "src/**/*.py", "main.py", "routers/*.py"]
compatible_with: [claude, gemini, cursor, windsurf, copilot, antigravity]
status: stable
version: "1.0.0"
---

# FastAPI Clean Architecture Standards

> [!IMPORTANT]
> APIs desenvolvidas com FastAPI devem manter estrita separação de responsabilidades. Controladores (Routers) NÃO devem conter regras de negócio complexas ou consultas diretas ao banco de dados.

---

## 1. Estrutura Canônica de Diretórios

```
src/
├── api/
│   ├── dependencies.py      # Injeção de dependências compartilhadas (Auth, DB Session)
│   └── v1/
│       ├── router.py        # Agregador de rotas v1 (APIRouter)
│       └── endpoints/       # Controladores HTTP (Users, Orders, etc.)
├── core/
│   ├── config.py            # Pydantic BaseSettings (.env centralizado)
│   ├── database.py          # SQLAlchemy / SQLModel / Engine & Sessionmaker
│   └── exceptions.py        # Exceções de domínio e handlers HTTP
├── models/                  # Entidades de persistência (ORM SQLAlchemy / SQLModel)
├── schemas/                 # DTOs de validação e serialização (Pydantic v2 BaseModel)
├── repositories/            # Camada de acesso a dados (CRUD desacoplado)
├── services/                # Regras de negócio e orquestração
└── main.py                  # Ponto de entrada da aplicação FastAPI
```

---

## 2. Padrões por Camada

### 2.1 Schemas (Pydantic v2)
* Use `model_config = ConfigDict(from_attributes=True)` para serialização a partir de ORM.
* Separe sempre: `CreateSchema`, `UpdateSchema`, `ResponseSchema`.

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 2.2 Injeção de Dependências & Handlers HTTP (Routers)
* Routers recebem parâmetros validados via Pydantic e delegam execução para a camada de serviço através de `Depends()`.

```python
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies import get_db
from src.schemas.user import UserCreate, UserResponse
from src.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(UserService.get_instance),
):
    return await service.register_user(payload)
```

---

## 3. Tratamento Centralizado de Exceções

Crie exceções de domínio no `core/exceptions.py` e registre handlers globais no `main.py`:

```python
# core/exceptions.py
class DomainException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.core.exceptions import DomainException

app = FastAPI(title="Minha API Clean", version="1.0.0")

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.message, "path": str(request.url.path)},
    )
```

---

## 4. O que NUNCA fazer

* ❌ Executar consultas de banco de dados (`session.execute()`, queries SQL) diretamente dentro da função do endpoint.
* ❌ Usar `except Exception:` genérico sem re-lançar ou sem tratamento estruturado.
* ❌ Retornar modelos de ORM brutos no response sem passar por um `response_model` do Pydantic.
