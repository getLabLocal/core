DC := docker compose -f ./docker-compose.yml

.PHONY: up down logs shell migrate migrations seed superuser test dev

up:
	$(DC) up --build

down:
	$(DC) down

logs:
	$(DC) logs -f web

shell:
	$(DC) exec web python manage.py shell

migrate:
	$(DC) exec web python manage.py migrate

migrations:
	$(DC) exec web python manage.py makemigrations

seed:
	$(DC) exec web python manage.py seed_biomarkers

superuser:
	$(DC) exec web python manage.py createsuperuser

test:
	$(DC) exec web python manage.py test

dev:
	uv run python manage.py runserver 0.0.0.0:8000
