# Roteiro de homologação WhatsMiau

Este roteiro prepara um teste real controlado. Ele não autoriza disparos por si só. Execute somente após o responsável informar uma instância de teste, uma chave por ambiente e um número que tenha consentido explicitamente em receber a mensagem.

## 1. Preparação segura

1. Defina uma janela de teste e identifique a loja que será homologada.
2. Use uma instância WhatsMiau de teste ou uma instância cuja operação possa ser acompanhada.
3. Obtenha autorização explícita do titular do número de destino.
4. Não registre chaves ou segredos em tickets, capturas de tela ou banco de dados.
5. Ative a trava global de homologação no `.env`:

```dotenv
REMINDER_HOMOLOGATION_ONLY="true"
WHATS_MIAU_LOJA_TESTE_KEY="valor-fornecido-fora-do-repositorio"
WHATS_MIAU_LOJA_TESTE_WEBHOOK_SECRET="segredo-aleatorio-fora-do-repositorio"
```

Recrie `backend` e `reminder-worker` após alterar o ambiente.

## 2. Banco e serviços

```powershell
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose up --build -d
docker compose ps
docker compose exec backend alembic current
```

Confirme que backend, frontend e PostgreSQL estão saudáveis e que o worker está ativo sem erros.

## 3. Configuração administrativa

No painel `/app/admin`:

1. Selecione a loja de teste.
2. Informe o identificador real da instância.
3. Informe somente os nomes `WHATS_MIAU_LOJA_TESTE_KEY` e `WHATS_MIAU_LOJA_TESTE_WEBHOOK_SECRET`.
4. Autorize o número de homologação e confirme que o titular consentiu.
5. Verifique a conexão. O resultado esperado é `open`.

O painel deve mostrar somente os quatro últimos dígitos do número autorizado e nunca deve exibir os valores das variáveis.

## 4. Webhook de entrega

Configure na WhatsMiau uma URL HTTPS pública apontando para:

```text
https://SEU_BACKEND/webhooks/whatsmiau/ID_DA_LOJA
```

Inclua o header customizado:

```text
X-Delmont-Webhook-Secret: valor de WHATS_MIAU_LOJA_TESTE_WEBHOOK_SECRET
```

Habilite o evento `messages.update`. Webhooks com segredo incorreto ou instância diferente devem receber rejeição e não alterar lembretes.

## 5. Envio controlado

1. Cadastre um cliente de teste usando exatamente o número autorizado.
2. Registre o consentimento e sua origem.
3. Crie um modelo claramente identificado como homologação.
4. Na área comercial, clique em **Verificar conexão**.
5. Agende um único lembrete para alguns minutos à frente.
6. Registre o ID do lembrete e o horário programado, sem copiar telefone ou credenciais.
7. Aguarde o worker; não execute chamadas manuais de envio.

Evidências mínimas esperadas:

- uma tentativa persistida antes do HTTP;
- `provider_message_id` retornado pela WhatsMiau;
- estado `accepted` após resposta de envio;
- `delivered` após `DELIVERY_ACK` ou `read` após `READ`;
- horários de tentativa, aceitação e entrega/leitura;
- apenas uma requisição de envio para o lembrete.

Uma resposta aceita não deve ser registrada como entrega sem o webhook correspondente.

## 6. Cenários de confiabilidade

Execute um cenário por vez, sempre com um novo lembrete de teste:

1. Cancele antes do horário e confirme ausência de tentativa de envio.
2. Revogue o consentimento antes do horário e confirme falha de validação sem HTTP de envio.
3. Desconecte a instância, aguarde `retry_wait`, reconecte e confirme um único envio.
4. Reinicie o worker antes do claim e confirme processamento normal.
5. Reinicie durante um envio controladamente bloqueado e confirme `uncertain`, sem retry automático.
6. Repita com a segunda loja e confirme que instância, credencial, histórico e webhook não se cruzam.

Não tente “resolver” um estado `uncertain` reenviando. Compare os registros da WhatsMiau e faça análise manual enquanto não existir consulta idempotente documentada.

## 7. Encerramento

1. Exporte somente IDs, estados e horários necessários ao relatório.
2. Remova ou revogue credenciais temporárias.
3. Pause a loja caso a homologação não tenha sido aprovada.
4. Restaure `REMINDER_HOMOLOGATION_ONLY` conforme a decisão de liberação.
5. Registre separadamente: aceito, entregue, lido, falhou ou incerto.

Sem `provider_message_id` e evidência do resultado do provedor, a homologação real permanece pendente.
