# Referência da API

Esta documentação descreve os contratos HTTP expostos pelo `journey-core-case`.

Para uma visão de execução rápida e do fluxo principal, consulte o [`README.md`](../README.md).

A documentação OpenAPI interativa também fica disponível enquanto a aplicação estiver em execução:

```text
http://127.0.0.1:8000/docs
```

## Base URL

Em execução local:

```text
http://127.0.0.1:8000
```

A API não implementa autenticação ou autorização, conforme o escopo do desafio.

---

# Visão geral

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health` | Verificar disponibilidade da aplicação |
| `POST` | `/patients` | Criar um Patient |
| `POST` | `/patients/{patient_id}/protocols` | Iniciar um protocolo |
| `POST` | `/protocol-sessions/{session_id}/answers` | Submeter uma resposta |
| `GET` | `/patients/{patient_id}/journey` | Consultar a Journey |
| `POST` | `/journeys/{journey_id}/tasks/{task_id}/complete` | Concluir uma Task |
| `POST` | `/followups/evaluate` | Avaliar elegibilidade de follow-up |
| `GET` | `/events?patient_id=...` | Consultar a trilha de eventos do Patient |

---

# Convenções

## Identificadores

Os identificadores de entidades são UUIDs.

Exemplos:

```text
patient_id
session_id
journey_id
task_id
event_id
```

Parâmetros que esperam UUID rejeitam valores malformados com HTTP `422`.

## Datas

`birth_date` utiliza formato ISO:

```text
YYYY-MM-DD
```

Timestamps de eventos utilizam ISO 8601 em UTC.

Exemplo:

```text
2026-08-25T14:14:40.254925Z
```

## Erros

Erros de domínio seguem o formato:

```json
{
  "error": "error_code",
  "message": "Human-readable message"
}
```

Erros de validação HTTP são deliberadamente sanitizados:

```json
{
  "error": "validation_error",
  "message": "Invalid request"
}
```

Valores enviados pelo usuário não são ecoados na resposta de erro.

---

# GET `/health`

Verifica se a aplicação está disponível.

## Request

Não possui parâmetros.

## Response

### `200 OK`

```json
{
  "status": "ok"
}
```

## Efeitos colaterais

Nenhum.

---

# POST `/patients`

Cria um novo Patient.

## Request

```json
{
  "phone": "+55 11 98888-1234",
  "name": "Paciente Teste",
  "birth_date": "1990-01-01",
  "sex": "M",
  "terms_accepted": true
}
```

### Campos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---:|---|
| `phone` | `string` | sim | Telefone operacional do Patient |
| `name` | `string` | sim | Nome do Patient |
| `birth_date` | `date` | sim | Data de nascimento |
| `sex` | `string` | sim | Sexo informado |
| `terms_accepted` | `boolean` | sim | Indica aceite dos termos |

## Response

### `201 Created`

```json
{
  "patient_id": "5d997c4f-592b-4e6f-8c58-0bb28bc2347b",
  "phone": "+55 11 98888-1234",
  "name": "Paciente Teste",
  "birth_date": "1990-01-01",
  "sex": "M",
  "terms_accepted": true
}
```

`phone_hash` e `patient_id_hash` são internos e não são expostos nesta resposta.

## Eventos emitidos

Sempre:

```text
patient_created
```

Quando `terms_accepted = true`:

```text
terms_accepted
```

## Possíveis erros

### `422 Unprocessable Entity`

Request incompatível com o schema.

```json
{
  "error": "validation_error",
  "message": "Invalid request"
}
```

---

# POST `/patients/{patient_id}/protocols`

Inicia uma nova sessão de protocolo para um Patient.

## Path parameters

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `patient_id` | UUID | Identificador interno do Patient |

## Request

```json
{
  "template_id": "phq9"
}
```

## Response

### `201 Created`

```json
{
  "session_id": "95eaf74e-8fd6-4c05-9a39-eaedaebb8cfa",
  "status": "in_progress",
  "prompt": "Nas últimas duas semanas, com que frequência você foi incomodado por…",
  "current_question": {
    "id": "1",
    "text": "Pouco interesse ou prazer em fazer as coisas",
    "type": "likert",
    "options": [
      {
        "value": 0,
        "label": "Nenhuma vez"
      },
      {
        "value": 1,
        "label": "Vários dias"
      },
      {
        "value": 2,
        "label": "Mais da metade dos dias"
      },
      {
        "value": 3,
        "label": "Quase todos os dias"
      }
    ]
  }
}
```

## Pré-condições

O Patient deve existir e ter:

```text
terms_accepted = true
```

## Eventos emitidos

Em caso de sucesso:

```text
protocol_started
```

Properties:

```json
{
  "template_id": "phq9",
  "template_version": "1.0"
}
```

## Possíveis erros

### `403 Forbidden`

Patient não aceitou os termos.

```json
{
  "error": "consent_required",
  "message": "Consent is required"
}
```

### `404 Not Found`

Patient inexistente:

```json
{
  "error": "patient_not_found",
  "message": "Patient not found"
}
```

Template inexistente:

```json
{
  "error": "protocol_template_not_found",
  "message": "Protocol template not found"
}
```

### `422 Unprocessable Entity`

UUID ou body inválido.

---

# POST `/protocol-sessions/{session_id}/answers`

Submete uma resposta para a questão atual de uma sessão de protocolo.

## Path parameters

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `session_id` | UUID | Identificador da ProtocolSession |

## Request

```json
{
  "question_id": "1",
  "value": 1
}
```

O `value` deve corresponder a uma das opções declaradas para a questão atual.

Valores booleanos não são aceitos como equivalentes a `0` ou `1`.

---

## Resposta enquanto o protocolo continua

### `200 OK`

```json
{
  "session_id": "95eaf74e-8fd6-4c05-9a39-eaedaebb8cfa",
  "status": "in_progress",
  "next_question": {
    "id": "2",
    "text": "Sentir-se para baixo, deprimido(a) ou sem esperança",
    "type": "likert",
    "options": [
      {
        "value": 0,
        "label": "Nenhuma vez"
      },
      {
        "value": 1,
        "label": "Vários dias"
      },
      {
        "value": 2,
        "label": "Mais da metade dos dias"
      },
      {
        "value": 3,
        "label": "Quase todos os dias"
      }
    ]
  },
  "score": null,
  "ended_by_skip": null
}
```

Nenhum evento de conclusão é emitido enquanto a sessão permanece `in_progress`.

---

## Resposta após encerramento por skip

Exemplo: respostas `1` e `1` nas duas primeiras questões do PHQ-9.

### `200 OK`

```json
{
  "session_id": "95eaf74e-8fd6-4c05-9a39-eaedaebb8cfa",
  "status": "completed",
  "next_question": null,
  "score": 2,
  "ended_by_skip": true
}
```

---

## Resposta após conclusão normal

Quando todas as questões necessárias são respondidas:

```json
{
  "session_id": "95eaf74e-8fd6-4c05-9a39-eaedaebb8cfa",
  "status": "completed",
  "next_question": null,
  "score": 13,
  "ended_by_skip": false
}
```

## Efeitos da conclusão

Quando a sessão passa para `completed`:

1. o score final é persistido;
2. é emitido `protocol_completed`;
3. uma Journey é criada;
4. é emitido `journey_created`.

`protocol_completed` contém:

```json
{
  "template_id": "phq9",
  "template_version": "1.0",
  "score": 2,
  "ended_by_skip": true
}
```

## Possíveis erros

### `404 Not Found`

Sessão inexistente:

```json
{
  "error": "protocol_session_not_found",
  "message": "Protocol session not found"
}
```

### `409 Conflict`

Sessão já concluída:

```json
{
  "error": "protocol_already_completed",
  "message": "Protocol is already completed"
}
```

Questão enviada não corresponde ao estado atual:

```json
{
  "error": "question_mismatch",
  "message": "Question does not match current protocol state"
}
```

### `422 Unprocessable Entity`

Resposta semanticamente inválida:

```json
{
  "error": "invalid_answer",
  "message": "Invalid answer"
}
```

Ou erro de schema HTTP:

```json
{
  "error": "validation_error",
  "message": "Invalid request"
}
```

Uma resposta inválida não avança a sessão, não cria Journey e não emite `protocol_completed`.

---

# GET `/patients/{patient_id}/journey`

Retorna a Journey associada ao Patient.

## Path parameters

| Parâmetro | Tipo |
|---|---|
| `patient_id` | UUID |

## Response

### `200 OK`

```json
{
  "journey_id": "5c88976c-81c4-4929-b44a-e5966933c04a",
  "status": "em_andamento",
  "objective": "Acompanhamento após protocolo clínico",
  "tasks": [
    {
      "task_id": "bda841fa-c7a6-4acb-9914-b66de475f425",
      "title": "Realizar acompanhamento",
      "status": "in_progress"
    }
  ]
}
```

## Status possíveis da Journey

```text
em_andamento
concluida
```

A implementação atual cria a Journey em `em_andamento`.

## Possíveis erros

### `404 Not Found`

Patient inexistente:

```json
{
  "error": "patient_not_found",
  "message": "Patient not found"
}
```

Patient existe, mas ainda não possui Journey:

```json
{
  "error": "journey_not_found",
  "message": "Journey not found"
}
```

### `422 Unprocessable Entity`

`patient_id` malformado.

---

# POST `/journeys/{journey_id}/tasks/{task_id}/complete`

Marca uma Task da Journey como concluída.

## Path parameters

| Parâmetro | Tipo |
|---|---|
| `journey_id` | UUID |
| `task_id` | UUID |

## Request

Não possui body.

## Response

### `200 OK`

```json
{
  "journey_id": "5c88976c-81c4-4929-b44a-e5966933c04a",
  "task_id": "bda841fa-c7a6-4acb-9914-b66de475f425",
  "status": "completed"
}
```

## Evento emitido

```text
task_completed
```

Properties:

```json
{
  "journey_id": "5c88976c-81c4-4929-b44a-e5966933c04a",
  "task_id": "bda841fa-c7a6-4acb-9914-b66de475f425"
}
```

A conclusão da Task não altera automaticamente o status da Journey.

## Possíveis erros

### `404 Not Found`

Journey inexistente:

```json
{
  "error": "journey_not_found",
  "message": "Journey not found"
}
```

Task inexistente:

```json
{
  "error": "task_not_found",
  "message": "Task not found"
}
```

### `409 Conflict`

Task já concluída:

```json
{
  "error": "task_already_completed",
  "message": "Task is already completed"
}
```

### `422 Unprocessable Entity`

UUID malformado.

---

# POST `/followups/evaluate`

Avalia deterministicamente se um Patient está elegível para follow-up.

Uma avaliação inelegível continua sendo uma execução válida da API e, portanto, retorna HTTP `200`.

## Request

```json
{
  "patient_id": "5d997c4f-592b-4e6f-8c58-0bb28bc2347b"
}
```

---

## Patient elegível

### `200 OK`

```json
{
  "eligible": true,
  "template_key": "checkin_adesao",
  "reason": null
}
```

Evento emitido:

```text
followup_eligible
```

Properties:

```json
{
  "template_key": "checkin_adesao"
}
```

---

## Patient inelegível

### `200 OK`

Exemplo de cooldown:

```json
{
  "eligible": false,
  "template_key": null,
  "reason": "cooldown"
}
```

Evento emitido:

```text
followup_skipped
```

Properties:

```json
{
  "reason": "cooldown"
}
```

## Motivos possíveis

```text
missing_consent
protocol_not_completed
journey_not_active
no_active_task
cooldown
```

As regras são avaliadas em ordem e o primeiro requisito não satisfeito determina o motivo.

## Possíveis erros

### `404 Not Found`

Patient inexistente:

```json
{
  "error": "patient_not_found",
  "message": "Patient not found"
}
```

### `422 Unprocessable Entity`

Body inválido ou UUID malformado.

## Observação sobre cooldown

O cooldown considera eventos anteriores:

```text
followup_eligible
```

dentro das últimas 72 horas.

Eventos `followup_skipped` não reiniciam o cooldown.

---

# GET `/events`

Retorna a trilha pseudonimizada de eventos de um Patient.

## Query parameters

| Parâmetro | Tipo | Obrigatório |
|---|---|---:|
| `patient_id` | UUID | sim |

Exemplo:

```text
GET /events?patient_id=5d997c4f-592b-4e6f-8c58-0bb28bc2347b
```

O endpoint recebe o `patient_id` interno.

O cliente não consulta eventos diretamente por `patient_id_hash`.

## Response

### `200 OK`

```json
[
  {
    "event_id": "64f33d8b-dac1-44e8-ac69-a0fda79112ab",
    "occurred_at": "2026-08-25T14:06:22.598738Z",
    "event_name": "patient_created",
    "patient_id_hash": "0a7a14ab8f9030e25166cbde9720479aeff221e0d353e0f62924b3d6579f272f",
    "properties": {}
  },
  {
    "event_id": "327f6f14-4b95-4745-9ef1-1dd07f72b5b5",
    "occurred_at": "2026-08-25T14:12:41.109736Z",
    "event_name": "protocol_completed",
    "patient_id_hash": "0a7a14ab8f9030e25166cbde9720479aeff221e0d353e0f62924b3d6579f272f",
    "properties": {
      "template_id": "phq9",
      "template_version": "1.0",
      "score": 2,
      "ended_by_skip": true
    }
  }
]
```

Todos os eventos pertencentes ao mesmo Patient utilizam o mesmo `patient_id_hash`.

## Dados ausentes por design

A trilha não contém:

```text
phone
name
birth_date
```

O `patient_id_hash` é uma identidade pseudonimizada separada do `phone_hash`.

## Possíveis erros

### `404 Not Found`

Patient inexistente:

```json
{
  "error": "patient_not_found",
  "message": "Patient not found"
}
```

### `422 Unprocessable Entity`

`patient_id` ausente ou malformado.

Um `patient_id_hash` também não pode ser utilizado no lugar do UUID interno.

---

# Taxonomia de eventos

| Evento | Quando é emitido | Properties |
|---|---|---|
| `patient_created` | Patient criado | `{}` |
| `terms_accepted` | Patient criado com termos aceitos | `{}` |
| `protocol_started` | ProtocolSession iniciada | `template_id`, `template_version` |
| `protocol_completed` | Protocolo concluído ou encerrado por skip | `template_id`, `template_version`, `score`, `ended_by_skip` |
| `journey_created` | Journey criada após conclusão do protocolo | `journey_id`, `objective` |
| `task_completed` | Task concluída | `journey_id`, `task_id` |
| `followup_eligible` | Follow-up elegível | `template_key` |
| `followup_skipped` | Follow-up não elegível | `reason` |

---

# Status codes

| Código | Uso |
|---|---|
| `200` | Consulta, atualização ou avaliação executada com sucesso |
| `201` | Recurso criado com sucesso |
| `403` | Operação bloqueada por falta de consentimento |
| `404` | Entidade ou template não encontrado |
| `409` | Operação incompatível com o estado atual |
| `422` | Request ou resposta de protocolo inválida |
| `500` | Erro interno ou configuração de regra não suportada |

Erros de configuração interna são retornados de forma sanitizada:

```json
{
  "error": "internal_error",
  "message": "Internal server error"
}
```

---

# OpenAPI

O FastAPI gera automaticamente o schema OpenAPI da aplicação.

Com a API em execução:

```text
Swagger UI
http://127.0.0.1:8000/docs
```

O Swagger deve ser considerado a referência interativa dos schemas HTTP, enquanto este documento registra também semântica, pré-condições e efeitos colaterais relevantes.
