# AINA Health — `journey-core`

## Engineering Specification — implementation contract

**Stack:** Python 3.12 · FastAPI · Pydantic v2 · pytest  
**Persistence:** In-memory  
**Architecture:** API → Application Services → Domain/Engines → Repository

> This document records the approved implementation contract for the repository. The original specification was not present in the repository when Etapa 4 started; the existing approved domain/repository decisions are preserved, and the Event Store + LGPD decisions below are now explicit.

## Roadmap

1. Bootstrap — **DONE**
2. Domain Models — **DONE**
3. Repositories — **DONE**
4. Event Store + LGPD — **IN PROGRESS**
5. Declarative Protocol Templates
6. Protocol Engine
7. Journey + Tasks
8. Follow-up Rules + Engine
9. Application Services
10. API
11. Integration / Acceptance Tests
12. README + Final Polish

## Architecture

```text
API
 │
 ▼
Application Services
 │
 ├── Domain / Engines
 ├── Repositories
 └── Event Service
```

Repositories only persist and recover state. Domain models do not depend on repositories, services, or FastAPI.

## Event Store + LGPD

Business event emission follows:

```text
Application Service
        ↓
   EventService
        ↓
 EventRepository
```

The API must not emit business events directly. `EventService` is responsible for constructing and persisting the event envelope. It generates `event_id`, generates a UTC timezone-aware `occurred_at`, preserves the typed event name and properties, and delegates persistence to `EventRepository`.

`EventRepository` remains append-only and exposes only append/list operations. It must not provide update or delete operations.

The event envelope is:

```text
event_id
occurred_at
event_name
patient_id_hash
properties
```

Events must never contain `phone`, `name`, or `birth_date`, including inside `properties`. The protection is structural: event-specific Pydantic property schemas expose only non-sensitive fields. No generic PII detector or sanitizer is required.

## Event taxonomy

`EventName` is a `StrEnum` containing:

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

## Typed event properties

The following Pydantic schemas define the allowed properties:

- `PatientCreatedProperties`: empty
- `TermsAcceptedProperties`: empty
- `ProtocolStartedProperties`: `template_id`, `template_version`
- `ProtocolCompletedProperties`: `template_id`, `template_version`, `score`, `ended_by_skip`
- `JourneyCreatedProperties`: `journey_id`, `objective`
- `TaskCompletedProperties`: `journey_id`, `task_id`
- `FollowupEligibleProperties`: `template_key`
- `FollowupSkippedProperties`: `reason`

`FollowupSkipReason` is a domain `StrEnum` containing:

```text
missing_consent
protocol_not_completed
journey_not_active
no_active_task
cooldown
```

## Phone hashing

Operational patient data may retain `phone` and `phone_hash` in the `Patient` model. The phone must never cross the event boundary.

Phone hashing is an isolated security concern, not authentication. The salt is supplied by the `PHONE_HASH_SALT` environment variable and is never hardcoded. The salt must be injectable for deterministic tests.

Normalization is deterministic and intentionally simple for this challenge: remove formatting and retain digits only. Hashing uses SHA-256 over:

```text
salt + normalized_phone
```

The system does not implement login, passwords, JWTs, authorization, or other authentication mechanisms.

## Future event query boundary

A future `GET /events?patient_id=<internal UUID>` endpoint will resolve the internal patient through `PatientRepository`, obtain `Patient.phone_hash`, and query `EventRepository.list_by_patient(phone_hash)`. The event store is keyed by the hash, while the API boundary uses the internal patient UUID.

## Etapa 4 scope boundary

This stage implements only Event Store + LGPD concerns:

- `EventService`;
- typed event properties;
- `FollowupSkipReason`;
- phone normalization and SHA-256 hashing;
- Event Store append-only behavior and tests.

The following remain for later stages: protocol JSON/template loading, engines, business application services, business endpoints, follow-up evaluation, external persistence, and authentication.
