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

A baseline inicializa o histórico e a migration seguinte cria as tabelas de autenticação, usuários, lojas e associações.

## Primeiro administrador

O administrador inicial nunca é criado automaticamente. Com os containers em execução, forneça os dados explicitamente e execute o comando administrativo:

```powershell
$env:ADMIN_NAME="Nome do administrador"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="use-uma-senha-forte-com-12-ou-mais-caracteres"
docker compose exec -e ADMIN_NAME -e ADMIN_EMAIL -e ADMIN_PASSWORD backend python -m app.cli.bootstrap_admin
Remove-Item Env:ADMIN_NAME, Env:ADMIN_EMAIL, Env:ADMIN_PASSWORD
```

O comando é idempotente: se o administrador já existir, não altera sua senha nem cria duplicatas. A senha não é exibida em logs. Em um terminal interativo, também é possível omitir `ADMIN_PASSWORD` e informá-la pelo prompt seguro.

## Autenticação e controle de acesso

- Sessões opacas armazenadas no PostgreSQL e enviadas em cookie `HttpOnly`.
- Cookie `Secure` habilitado automaticamente em `APP_ENVIRONMENT=production`.
- Proteção CSRF para operações autenticadas de escrita.
- Senhas armazenadas somente com Argon2id.
- Bloqueio temporário após tentativas excessivas de login.
- Perfis fixos `admin` e `collaborator`.
- Acesso de colaboradores limitado às lojas ativas associadas.

Endpoints disponíveis:

- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`
- `GET /users`, `POST /users`, `PATCH /users/{id}`
- `GET /stores`, `GET /stores/{id}`, `POST /stores`, `PATCH /stores/{id}`
- `GET /users/{id}/stores`, `PUT /users/{id}/stores`

### Módulo comercial

Clientes são sempre vinculados a uma loja e o telefone é normalizado para E.164. O cadastro não concede autorização para lembretes: o consentimento precisa ser registrado explicitamente, com sua origem, e todas as concessões e revogações permanecem no histórico.

- `GET /customers`, `POST /customers`
- `GET /customers/{id}`, `PATCH /customers/{id}`
- `POST /customers/{id}/consent`, `POST /customers/{id}/revoke-consent`
- `GET /message-templates`, `POST /message-templates`
- `GET /message-templates/{id}`, `PATCH /message-templates/{id}`
- `POST /message-templates/{id}/preview`
- `GET /reminders`, `POST /reminders`
- `GET /reminders/{id}`, `PATCH /reminders/{id}`
- `POST /reminders/{id}/cancel`
- `POST /reminders/cancel-product`

As consultas de clientes e modelos recebem `store_id` e o backend valida a autorização do usuário antes de consultar os dados. Modelos aceitam somente `{{nome}}`, `{{produto}}` e `{{loja}}`; modelos inativos não geram prévias operacionais.

A interface comercial fica em http://localhost:3000/app/commercial e acompanha a loja ativa selecionada no cabeçalho.

Os lembretes armazenam a mensagem final renderizada, produto de interesse, data e horário e um dos estados `pending`, `cancelled`, `completed` ou `failed`. A criação exige cliente ativo com consentimento e modelo ativo na mesma loja. Um índice único parcial no PostgreSQL impede lembretes pendentes duplicados mesmo sob concorrência. A rota `cancel-product` é idempotente e encerra as pendências do produto quando a venda é concluída.

Este módulo é um motor passivo nesta etapa: não há worker, scheduler ativo nem integração com WhatsMiau, portanto nenhum lembrete é disparado automaticamente.

## Testes e verificações

Backend:

```powershell
Set-Location backend
python -m pytest -q
```

Os testes de autenticação exigem PostgreSQL real e isolado. Execute pelo perfil de teste do Compose:

```powershell
docker compose --profile test run --rm backend-test
docker compose --profile test stop postgres-test
docker compose --profile test rm -f postgres-test
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

## Escopo atual

Autenticação, usuários, lojas, clientes, consentimentos, modelos de mensagens e o motor passivo de agendamento estão implementados. Ainda não estão implementados: WhatsMiau, worker de disparos, scheduler ativo, regras financeiras e integração com o sistema de caixa. A interface é responsiva e acompanha o esquema de cores claro ou escuro do sistema operacional.
