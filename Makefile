.PHONY: help build up down logs clean restart

help:
	@echo "Legal Diff - Makefile Commands"
	@echo ""
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - View logs (all services)"
	@echo "  make clean      - Remove all containers and volumes"
	@echo "  make restart    - Restart all services"
	@echo "  make shell-api  - Open shell in API container"
	@echo "  make shell-db   - Open PostgreSQL shell"
	@echo "  make test       - Run tests"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

restart:
	docker-compose restart

shell-api:
	docker-compose exec api bash

shell-db:
	docker-compose exec db psql -U user -d legal_diff

shell-frontend:
	docker-compose exec frontend sh

test:
	docker-compose exec api pytest

status:
	docker-compose ps

