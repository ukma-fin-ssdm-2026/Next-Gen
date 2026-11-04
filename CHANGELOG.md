# Changelog

Усі помітні зміни в проєкті документуються в цьому файлі.
Формат базується на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
і проєкт дотримується [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-04

### Added
- feat(migration): seed default categories in Alembic migration and add verification tests
- feat(persistence): implement PostgreSQL layer via SQLAlchemy/Alembic (ADR-002)
- feat(categories): implement category suggestions and moderation (FR-015 / US-010)
- feat(listings): integrate image storage lifecycle, cleanup on PATCH, and update RTM
- feat(api): add multipart image upload endpoint and API documentation
- feat(infra): configure external storage volume and image directory settings
- feat(storage): implement ImageStorage protocol, Pillow/HEIF processor, and unit tests
- feat(frontend): split landing page and catalog
- feat(auth): return users to requested page
- feat(frontend): add production routes and serving
- feat(frontend): add marketplace catalog MVP
- feat(moderation): admin withdraw with audit record (FR-011)
- feat(contact): authenticated seller contact endpoint (FR-010, SEC-002)
- feat(favorites): use CurrentUser instead of X-Actor-Id (FR-009)
- feat(favorites): API обраного /api/v1/favorites (FR-009)
- feat(favorites): домен, репозиторій і сервіс обраного (FR-009)
- feat(api): add GET /api/v1/listings/my endpoint, condition/images schemas, and API tests (FR-002..FR-005)
- feat(service): support listing images, condition, owner history (FR-002..FR-005), and decision table unit tests
- feat(domain): add ListingCondition, ListingImage, ImageStorage protocol, and list_by_owner
- feat(testing): add catalog filtering decision table tests and query normalization (Lab 7 bonus)

### Refactored
- refactor(frontend): improve accessibility semantics and eliminate regex ReDoS risk
- refactor(services): extract category resolution and cleanup in listing creation
- refactor(db): streamline ORM domain converters and eliminate mapping boilerplate
- refactor(storage): eliminate code duplication across image storage and test helpers

### Fixed
- fix(tests): prioritize explicit sqlalchemy.url and isolate round-trip test from DATABASE_URL
- fix(schema): resolve alembic check drift for comments and favorites pk constraint
- fix(models): synchronize table indexes with Alembic schema to eliminate autogenerate drift
- fix(alembic): specify create_type=False for columns to prevent duplicate enum error in Postgres
- fix(persistence): address PR review blockers and improvements
- fix(categories): isolate newly created category until approval commits
- fix(categories): serialize suggestion moderation with listing mutations and atomic creation
- fix(images): return HTTP 429 Too Many Requests on upload rate limit
- fix(listings,images): wire LocalImageStorage in DI, enforce require_current_user, and add TM-08 staged upload protections
- fix(docker): disable npm lifecycle scripts
- fix(auth): harden post-login return path
- fix(moderation): serialize concurrent withdrawals (Codex review)
- fix(validation): address round 3 review findings on category validation in listings and strict AST traceability
- fix(validation): address round 2 review findings on immutable PATCH, auth separation, and AST traceability
- fix(validation): address PR #200 review findings on FR-012, traceability, and NFR concurrency
- fix(favorites): прибирати зняте оголошення з обраного (FR-009)
- fix(security): omit contact from GET /api/v1/listings/my response (SEC-002)
- fix(listings): enforce >=1 image on create (FR-002) and prevent partial mutation on failed image update
- fix(security): disallow clear-text http:// in ALLOWED_IMAGE_PREFIXES for SonarQube

