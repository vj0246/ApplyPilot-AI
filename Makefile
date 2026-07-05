.PHONY: help start stop reset logs status

help:
	@echo ""
	@echo "  ApplyPilot — Commands"
	@echo "  ─────────────────────────────────────"
	@echo "  make start    Start everything"
	@echo "  make stop     Stop all containers"
	@echo "  make reset    Wipe data + restart fresh"
	@echo "  make logs     Live logs"
	@echo "  make status   Show container status"
	@echo ""

start:
	@cp -n .env.example .env 2>/dev/null || true
	@echo "⚠️  Make sure GROQ_API_KEY is set in .env"
	docker compose up -d --build
	@echo ""
	@echo "✅ ApplyPilot is starting..."
	@echo "   App:      http://localhost:3000"
	@echo "   API docs: http://localhost:8000/docs"
	@echo ""

stop:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build

logs:
	docker compose logs -f --tail=50


status:
	docker compose ps
