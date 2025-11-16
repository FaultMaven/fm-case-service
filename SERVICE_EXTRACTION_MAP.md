# Case Service Extraction Map

## Source Files (from FaultMaven monolith)

| Monolith File | Destination | Action |
|---------------|-------------|--------|
| faultmaven/models/case.py | src/case_service/domain/models/case.py | Extract + enhance (add org_id, team_id) |
| faultmaven/services/domain/case_service.py | src/case_service/domain/services/case_service.py | Extract business logic |
| faultmaven/api/v1/routes/case.py | src/case_service/api/routes/cases.py | Extract API endpoints |
| faultmaven/infrastructure/persistence/case_repository.py | src/case_service/infrastructure/persistence/repository.py | Extract data access |
| faultmaven/services/domain/case_status_manager.py | src/case_service/domain/services/status_manager.py | Extract status management |

## Database Tables (exclusive ownership)

| Table Name | Source Schema | Action |
|------------|---------------|--------|
| cases | 001_initial_hybrid_schema.sql | MIGRATE to fm_case database |
| case_messages | 001_initial_hybrid_schema.sql | MIGRATE to fm_case database |
| case_status_transitions | 001_initial_hybrid_schema.sql | MIGRATE to fm_case database |
| case_tags | 001_initial_hybrid_schema.sql | MIGRATE to fm_case database |

## Events Published

| Event Name | AsyncAPI Schema | Trigger |
|------------|-----------------|---------|
| case.created.v1 | contracts/asyncapi/case-events.yaml | POST /v1/cases |
| case.updated.v1 | contracts/asyncapi/case-events.yaml | PUT /v1/cases/{id} |
| case.status_changed.v1 | contracts/asyncapi/case-events.yaml | POST /v1/cases/{id}/status |
| case.deleted.v1 | contracts/asyncapi/case-events.yaml | DELETE /v1/cases/{id} |
| case.message.added.v1 | contracts/asyncapi/case-events.yaml | POST /v1/cases/{id}/messages |

## Events Consumed

| Event Name | Source Service | Action |
|------------|----------------|--------|
| evidence.uploaded.v1 | Evidence Service | Link evidence to case |
| investigation.completed.v1 | Investigation Service | Update case status |
| auth.user.deleted.v1 | Auth Service | Cascade delete user's cases |

## API Dependencies

| Dependency | Purpose | Fallback Strategy |
|------------|---------|-------------------|
| Auth Service | Validate user tokens | Circuit breaker (deny if down) |
| Session Service | Get active session | Circuit breaker (return 503) |

## Migration Checklist

- [ ] Extract domain models (Case, CaseMessage, CaseStatusTransition)
- [ ] Extract business logic (CaseService with validation rules)
- [ ] Extract API routes (CRUD + status transitions)
- [ ] Extract repository (PostgreSQL data access)
- [ ] Create database migration scripts (001_initial_schema.sql)
- [ ] Implement event publishing (outbox pattern)
- [ ] Implement event consumption (inbox pattern)
- [ ] Add circuit breakers for auth/session dependencies
- [ ] Write unit tests (80%+ coverage)
- [ ] Write integration tests (DB + events)
- [ ] Write contract tests (provider verification)
