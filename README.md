# Delmont Business

Base inicial de um sistema independente para lembretes comerciais e inteligência financeira de lojas físicas. Esta primeira task entrega somente a estrutura técnica: frontend, API, banco, migrations, testes e ambiente local com Docker.

## Stack

- Frontend: Next.js 16, React 19, TypeScript e Tailwind CSS 4
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 e Alembic
- Banco de dados: PostgreSQL 16
- Infraestrutura local: Docker Compose
- Testes do backend: pytest

## Pré-requisitos

Para executar tudo com Docker, basta ter Docker Desktop (ou Docker Engine) com o plugin Compose. Para desenvolvimento fora dos containers:

- Node.js 20.9 ou superior
- Python 3.12
- PostgreSQL 16

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste os valores locais. O arquivo `.env` não é versionado.

No PowerShell:

```powershell
Copy-Item .env.example .env
```

As principais variáveis são:

- `APP_NAME` e `APP_ENVIRONMENT`: identificação e ambiente da API.
- `DATABASE_URL`: conexão usada ao executar o backend fora do Docker.
- `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD`: banco criado pelo Compose.
- `FRONTEND_PORT`, `BACKEND_PORT` e `POSTGRES_PORT`: portas publicadas no host.
- `NEXT_PUBLIC_API_URL`: endereço público da API acessível pelo navegador.

Os valores do arquivo de exemplo são apenas para desenvolvimento local e não devem ser reutilizados em produção.

## Inicialização com Docker

```powershell
docker compose up --build -d
docker compose ps
```

A aplicação fica disponível em:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Documentação da API: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Para encerrar os serviços sem remover os dados do PostgreSQL:

```powershell
docker compose down
```

## Desenvolvimento local

Backend:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend, em outro terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

## Migrations

Com os containers em execução:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Fora do Docker, a partir de `backend/` e com o ambiente virtual ativo:

```powershell
alembic upgrade head
alembic current
```

Uma baseline vazia inicializa o histórico de migrations sem criar tabelas de negócio nesta task.

## Testes e verificações

Backend:

```powershell
Set-Location backend
python -m pytest -q
```

Frontend:

```powershell
Set-Location frontend
npm run lint
npm run build
```

Validação integrada:

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
docker compose exec backend alembic upgrade head
```

## Escopo desta task

Não estão implementados ainda: autenticação, cadastro de clientes, WhatsMiau, agendamento, regras financeiras e integração com o sistema de caixa. A interface atual é uma prévia estrutural responsiva, com suporte ao esquema de cores claro e escuro do sistema operacional.
