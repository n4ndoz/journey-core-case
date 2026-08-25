# Regras de Domínio

Este documento descreve as principais regras de negócio do `journey-core-case`.

O objetivo aqui não é documentar os contratos HTTP nem a organização interna do código, mas tornar explícito o comportamento esperado do domínio.

Para contratos da API, consulte [`API_REFERENCE.md`](API_REFERENCE.md).

Para arquitetura e responsabilidades dos componentes, consulte [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

# Visão geral do fluxo

O fluxo principal do domínio é:

```text
Patient criado
    ↓
Consentimento aceito
    ↓
ProtocolSession iniciada
    ↓
Respostas submetidas
    ↓
Protocolo concluído
    ↓
Journey criada
    ↓
Task em andamento
    ↓
Follow-up avaliado
```

Eventos relevantes são registrados ao longo desse fluxo em uma trilha append-only pseudonimizada.

---

# 1. Patient e consentimento

Um `Patient` possui:

```text
patient_id
patient_id_hash
phone
phone_hash
name
birth_date
sex
terms_accepted
```

O `patient_id` é o identificador interno da entidade.

O consentimento é representado diretamente por:

```text
terms_accepted
```

Não existe uma entidade separada para consentimento.

## Regra de consentimento

Um protocolo só pode ser iniciado quando:

```text
terms_accepted = true
```

Caso contrário, a operação é recusada com:

```text
consent_required
```

O consentimento também é requisito para elegibilidade de follow-up.

## Eventos

A criação de um Patient sempre gera:

```text
patient_created
```

Se o Patient for criado com:

```text
terms_accepted = true
```

também é gerado:

```text
terms_accepted
```

---

# 2. ProtocolTemplate

O comportamento de um protocolo é definido por um template declarativo.

O template atual é:

```text
app/protocols/templates/phq9.json
```

Um `ProtocolTemplate` contém:

```text
template_id
version
name
prompt
questions
skip_rules
```

Cada questão possui:

```text
id
text
type
options
```

As referências internas do template são validadas.

Por exemplo:

- IDs de questões não podem ser duplicados;
- uma `skip_rule` não pode apontar para uma questão inexistente;
- uma condição não pode depender de uma questão inexistente.

Dessa forma, configurações estruturalmente inválidas são rejeitadas antes da execução do protocolo.

---

# 3. ProtocolSession

Uma execução de protocolo é representada por uma `ProtocolSession`.

Estados possíveis:

```text
in_progress
completed
```

Uma sessão guarda:

```text
session_id
patient_id
template_id
template_version
status
current_question_id
answers
score
ended_by_skip
```

A versão do template é armazenada na sessão.

Isso significa que uma sessão iniciada com determinada versão continua vinculada àquela versão durante sua execução.

---

# 4. Submissão de respostas

Uma resposta contém:

```text
question_id
value
answered_at
```

Para uma resposta ser aceita:

1. a sessão deve estar `in_progress`;
2. `question_id` deve corresponder à questão atual;
3. a questão deve existir no template;
4. o valor deve pertencer às opções permitidas para aquela questão;
5. valores booleanos não são considerados respostas numéricas válidas.

Por exemplo:

```text
true
```

não é aceito como equivalente a:

```text
1
```

mesmo que em Python `bool` seja uma especialização de `int`.

Essa validação é intencional para evitar coerções silenciosas.

## Questão fora de ordem

Enviar uma resposta para uma questão diferente de `current_question_id` gera:

```text
question_mismatch
```

A sessão não avança.

## Sessão já concluída

Uma sessão com:

```text
status = completed
```

não aceita novas respostas.

O resultado é:

```text
protocol_already_completed
```

---

# 5. Score do protocolo

O score é calculado pela soma das respostas numéricas aceitas:

```text
score = soma(values)
```

Não são aplicadas fórmulas clínicas adicionais.

O projeto não introduz:

```text
índices derivados
classificações clínicas adicionais
interpretação diagnóstica
```

além da soma exigida para o protocolo.

---

# 6. PHQ-9 e encerramento antecipado

O PHQ-9 possui nove questões com escala:

```text
0 = Nenhuma vez
1 = Vários dias
2 = Mais da metade dos dias
3 = Quase todos os dias
```

Após a segunda questão, a configuração contém uma regra equivalente a:

```text
sum(question_1, question_2) < 3
```

Se essa condição for verdadeira:

```text
action = end_block
```

O protocolo é concluído imediatamente.

Exemplo:

```text
Q1 = 1
Q2 = 1

score parcial = 2

2 < 3
```

Resultado:

```text
status = completed
score = 2
ended_by_skip = true
current_question_id = null
```

Se a soma não for menor que `3`, o protocolo continua normalmente.

A regra está declarada no JSON e é interpretada pelo `ProtocolEngine`; ela não depende de uma condição hardcoded para o identificador `phq9`.

---

# 7. Continuação e conclusão normal

Quando nenhuma regra de skip encerra a sessão, o Engine procura a próxima questão na ordem declarada pelo template.

Se houver próxima questão:

```text
action = continue
```

A sessão permanece:

```text
status = in_progress
```

e `current_question_id` avança.

Quando a última questão é respondida:

```text
action = complete
```

A sessão passa para:

```text
status = completed
ended_by_skip = false
```

O score corresponde à soma de todas as respostas registradas.

---

# 8. Conclusão do protocolo

Quando uma ProtocolSession é concluída, seja normalmente ou por skip:

1. o estado da sessão é atualizado;
2. o score é persistido;
3. `current_question_id` passa para `null`;
4. é emitido `protocol_completed`;
5. uma Journey é criada.

O evento `protocol_completed` contém:

```text
template_id
template_version
score
ended_by_skip
```

Uma Journey não pode ser criada a partir de uma sessão que ainda esteja `in_progress`.

Nesse caso:

```text
protocol_not_completed
```

é retornado.

---

# 9. Journey

Após a conclusão de um protocolo, é criada uma Journey com:

```text
status = em_andamento
objective = "Acompanhamento após protocolo clínico"
```

Estados definidos para Journey:

```text
em_andamento
concluida
```

A implementação atual cria Journeys apenas em:

```text
em_andamento
```

e não implementa uma transição automática para `concluida`.

---

# 10. Tasks

A Journey inicial possui uma Task:

```text
title = "Realizar acompanhamento"
status = in_progress
```

Estados possíveis:

```text
in_progress
completed
```

Ao concluir a Task:

```text
in_progress → completed
```

é emitido:

```text
task_completed
```

com:

```text
journey_id
task_id
```

Uma Task já concluída não pode ser concluída novamente.

Nesse caso:

```text
task_already_completed
```

é retornado.

A repetição da chamada também não gera um novo evento `task_completed`.

---

# 11. Status da Journey após concluir Tasks

A conclusão da última Task não altera automaticamente:

```text
Journey.status
```

Portanto:

```text
Task = completed
Journey = em_andamento
```

é um estado válido na implementação atual.

Essa decisão foi tomada porque o desafio não especifica uma regra de conclusão automática da Journey.

Isso também permite que a regra:

```text
active_task_required
```

distinga uma Journey ativa que ainda possui trabalho pendente de uma Journey sem Tasks ativas.

---

# 12. Follow-up

O follow-up é uma decisão determinística.

A configuração atual está em:

```text
app/followups/rules/default.json
```

e possui:

```text
template_key = checkin_adesao
cooldown_hours = 72
```

As regras são avaliadas na ordem definida pela configuração.

---

# 13. Regras de elegibilidade de follow-up

Para ser elegível, todas as condições abaixo devem ser satisfeitas:

```text
1. terms accepted
2. protocol completed
3. Journey ativa
4. pelo menos uma Task ativa
5. cooldown expirado
```

Em termos do estado atual:

```text
terms_accepted = true

AND

existe ProtocolSession com:
status = completed

AND

Journey.status = em_andamento

AND

existe Task com:
status = in_progress

AND

não existe followup_eligible nas últimas 72 horas
```

O `FollowupEngine` avalia essas condições deterministicamente.

---

# 14. Precedência das regras de follow-up

As regras são avaliadas sequencialmente.

A primeira regra que falha encerra a avaliação.

A ordem atual é:

```text
missing_consent
        ↓
protocol_not_completed
        ↓
journey_not_active
        ↓
no_active_task
        ↓
cooldown
```

Isso significa que um Patient pode falhar em mais de uma condição, mas apenas a primeira razão aplicável é retornada.

Exemplo:

```text
terms_accepted = true
protocol_completed = false
Journey inexistente
```

O resultado é:

```text
protocol_not_completed
```

e não:

```text
journey_not_active
```

---

# 15. Resultado elegível

Quando todas as regras passam:

```text
eligible = true
template_key = checkin_adesao
reason = null
```

É emitido:

```text
followup_eligible
```

com:

```json
{
  "template_key": "checkin_adesao"
}
```

Nenhuma mensagem real é enviada.

O domínio apenas registra que um follow-up está elegível.

---

# 16. Resultado inelegível

Quando uma regra falha:

```text
eligible = false
template_key = null
reason = <typed reason>
```

É emitido:

```text
followup_skipped
```

com a razão correspondente.

Razões possíveis:

```text
missing_consent
protocol_not_completed
journey_not_active
no_active_task
cooldown
```

---

# 17. Cooldown de 72 horas

O cooldown utiliza como referência o evento mais recente:

```text
followup_eligible
```

do mesmo Patient.

Eventos:

```text
followup_skipped
```

não iniciam nem renovam cooldown.

Se não existir nenhum `followup_eligible` anterior:

```text
cooldown = expirado
```

Se existir:

```text
elapsed = evaluated_at - last_followup_eligible_at
```

A regra é:

```text
elapsed >= 72 horas
```

Portanto:

```text
71h59m59s → bloqueado
72h00m00s → elegível
```

A fronteira de exatamente 72 horas é inclusiva.

---

# 18. Eventos

A taxonomia do domínio é:

```text
patient_created
terms_accepted
protocol_started
protocol_completed
journey_created
task_completed
followup_eligible
followup_skipped
```

Os eventos possuem o envelope:

```text
event_id
occurred_at
event_name
patient_id_hash
properties
```

Cada tipo possui um conjunto explícito de `properties`.

---

# 19. PII e identidade de eventos

Eventos não utilizam:

```text
phone
name
birth_date
```

como propriedades.

Também não utilizam o telefone como chave da trilha.

A identidade utilizada é:

```text
patient_id_hash
```

derivada do identificador interno do Patient.

O `phone_hash` possui uma responsabilidade separada.

Assim:

```text
phone_hash
```

representa um hash derivado do telefone, enquanto:

```text
patient_id_hash
```

representa a identidade pseudonimizada da entidade Patient na trilha de eventos.

Essa distinção evita que dois Patients com o mesmo telefone compartilhem histórico de eventos ou cooldown.

---

# 20. Imutabilidade da trilha de eventos

Eventos são tratados como fatos append-only.

Não existem operações de:

```text
update event
delete event
```

no Event Repository.

Além disso, cópias profundas são utilizadas nas fronteiras de leitura e escrita para impedir alteração indireta do histórico através de referências Python compartilhadas.

---

# 21. Múltiplas sessões de protocolo

A implementação não impõe unicidade de ProtocolSession por Patient.

Portanto, um mesmo Patient pode possuir múltiplas sessões.

Cada início bem-sucedido gera:

```text
protocol_started
```

e cada sessão concluída pode gerar:

```text
protocol_completed
```

O challenge não define uma política de:

```text
cancelamento
expiração
substituição
sessão única
```

Por isso, nenhuma regra adicional foi criada.

---

# 22. Unicidade de telefone

A implementação não considera o telefone como identificador único do Patient.

Dois registros diferentes podem possuir o mesmo telefone.

Nesse caso:

```text
patient_id A != patient_id B
```

e:

```text
patient_id_hash A != patient_id_hash B
```

mesmo que:

```text
phone_hash A == phone_hash B
```

Cada Patient mantém seu próprio estado e sua própria trilha de eventos.

---

# 23. Tabela resumida de transições

| Entidade | Estado inicial | Ação | Estado resultante |
|---|---|---|---|
| Patient | criado | `terms_accepted = true` | apto a iniciar protocolo |
| ProtocolSession | `in_progress` | resposta válida intermediária | `in_progress` |
| ProtocolSession | `in_progress` | skip rule satisfeita | `completed` |
| ProtocolSession | `in_progress` | última questão respondida | `completed` |
| Journey | inexistente | protocolo concluído | `em_andamento` |
| Task | `in_progress` | completar Task | `completed` |
| Journey | `em_andamento` | Task concluída | `em_andamento` |
| Follow-up | não avaliado | regras aprovadas | `eligible = true` |
| Follow-up | não avaliado | regra falha | `eligible = false` |

---

# 24. Invariantes principais

As principais invariantes do domínio podem ser resumidas como:

```text
Sem consentimento
→ protocolo não inicia
```

```text
Resposta fora de ordem
→ sessão não avança
```

```text
Resposta inválida
→ sessão não avança
```

```text
Protocolo concluído
→ não aceita novas respostas
```

```text
Journey
→ só é criada após protocolo concluído
```

```text
Task concluída
→ não pode ser concluída novamente
```

```text
Follow-up elegível
→ exige consentimento + protocolo + Journey + Task ativa + cooldown
```

```text
Evento
→ não carrega PII em claro
```

```text
Cooldown
→ isolado por patient_id_hash
```

---

# 25. Escopo clínico

O projeto implementa o comportamento técnico do protocolo solicitado no desafio.

Ele não realiza:

```text
diagnóstico
interpretação clínica
recomendação médica
classificação de gravidade adicional
conduta terapêutica
```

O score é apenas a soma das respostas conforme a configuração.

O domínio foi deliberadamente mantido restrito às regras necessárias para o exercício.

---

# Resumo

O comportamento central pode ser condensado em:

```text
Consentimento controla entrada
        ↓
Template controla protocolo
        ↓
Engine controla progressão
        ↓
Conclusão cria Journey
        ↓
Tasks representam acompanhamento
        ↓
Regras declarativas avaliam follow-up
        ↓
Eventos registram fatos sem PII em claro
```

As regras foram mantidas explícitas e determinísticas para que o resultado de cada operação possa ser reproduzido e validado por testes.
