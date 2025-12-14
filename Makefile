# =============================================================================
# Discord Music Bot - Makefile
# =============================================================================

.PHONY: help build run clean test lint docker-build docker-run docker-stop \
        sqlc-generate migrate-create dev deps install

# Variables
BINARY_NAME=music-bot
MAIN_PATH=./cmd/bot/main.go
BUILD_DIR=.
DOCKER_IMAGE=nooblearn2code/discord-music-bot
VERSION?=2.0.0

# Database
POSTGRES_USER=music_bot
POSTGRES_PASSWORD=music_bot_db_pass
POSTGRES_DB=music_bot
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgres://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)?sslmode=disable

# Database production
POSTGRES_HOST_PROD=postgres
DATABASE_URL_PROD=postgres://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST_PROD):$(POSTGRES_PORT)/$(POSTGRES_DB)?sslmode=disable

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo '==================================================================='
	@echo 'Discord Music Bot - Make Commands'
	@echo '==================================================================='
	@echo ''
	@echo 'Usage:'
	@echo '  make <target>'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z_-]+:.*?##/ { printf "  %-20s %s\n", $$1, $$2 } /^##@/ { printf "\n%s\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ''

# =============================================================================
# Development
# =============================================================================

deps: ## Install dependencies
	@echo "📦 Installing dependencies..."
	@go mod download
	@go mod tidy

install: ## Install required tools (sqlc, goose)
	@echo "🔧 Installing development tools..."
	@go install github.com/sqlc-dev/sqlc/cmd/sqlc@latest
	@go install github.com/pressly/goose/v3/cmd/goose@latest

build: ## Build the bot binary
	@echo "🔨 Building $(BINARY_NAME)..."
	@go build -ldflags="-s -w -X main.Version=$(VERSION)" -o $(BUILD_DIR)/$(BINARY_NAME) $(MAIN_PATH)
	@echo "✅ Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

run: ## Run the bot locally
	@echo "🚀 Running bot..."
	@go run $(MAIN_PATH)

dev: ## Run bot in development mode with hot reload (requires air)
	@echo "🔥 Starting development server..."
	@air || (echo "⚠️  air not found, install with: go install github.com/cosmtrek/air@latest" && go run $(MAIN_PATH))

clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	@rm -f $(BINARY_NAME)
	@rm -rf ./cache/*
	@echo "✅ Clean complete"

# =============================================================================
# Testing & Quality
# =============================================================================

test: ## Run tests
	@echo "🧪 Running tests..."
	@go test -v -race -coverprofile=coverage.out ./...

test-coverage: test ## Run tests with coverage report
	@echo "📊 Generating coverage report..."
	@go tool cover -html=coverage.out -o coverage.html
	@echo "✅ Coverage report: coverage.html"

lint: ## Run linter
	@echo "🔍 Running linter..."
	@golangci-lint run ./... || echo "⚠️  golangci-lint not found, install from https://golangci-lint.run/usage/install/"

fmt: ## Format code
	@echo "💅 Formatting code..."
	@go fmt ./...
	@gofmt -s -w .

vet: ## Run go vet
	@echo "🔎 Running go vet..."
	@go vet ./...

# =============================================================================
# Database
# =============================================================================

sqlc-generate: ## Generate sqlc code from queries
	@echo "📝 Generating sqlc code..."
	@sqlc generate
	@echo "✅ sqlc generation complete"

migrate-create: ## Create a new migration (usage: make migrate-create NAME=migration_name)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME is required"; \
		echo "Usage: make migrate-create NAME=your_migration_name"; \
		exit 1; \
	fi
	@echo "📝 Creating migration: $(NAME)..."
	@timestamp=$$(date +%Y%m%d%H%M%S); \
	filename="db/migrations/$${timestamp}_$(NAME).sql"; \
	echo "-- +goose Up" > $$filename; \
	echo "-- SQL in this section is executed when the migration is applied." >> $$filename; \
	echo "" >> $$filename; \
	echo "" >> $$filename; \
	echo "-- +goose Down" >> $$filename; \
	echo "-- SQL in this section is executed when the migration is rolled back." >> $$filename; \
	echo "" >> $$filename; \
	echo "✅ Created migration: $$filename"

db-status: ## Show database migration status (requires DATABASE_URL)
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "❌ Error: DATABASE_URL environment variable is required"; \
		exit 1; \
	fi
	@echo "📊 Migration status:"
	@goose -dir db/migrations postgres "$(DATABASE_URL)" status

db-up: ## Run pending migrations (requires DATABASE_URL)
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "❌ Error: DATABASE_URL environment variable is required"; \
		exit 1; \
	fi
	@echo "⬆️  Running migrations..."
	@goose -dir db/migrations postgres "$(DATABASE_URL)" up

db-down: ## Rollback last migration (requires DATABASE_URL)
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "❌ Error: DATABASE_URL environment variable is required"; \
		exit 1; \
	fi
	@echo "⬇️  Rolling back migration..."
	@goose -dir db/migrations postgres "$(DATABASE_URL)" down

db-reset: ## Reset database (DOWN then UP)
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "❌ Error: DATABASE_URL environment variable is required"; \
		exit 1; \
	fi
	@echo "🔄 Resetting database..."
	@goose -dir db/migrations postgres "$(DATABASE_URL)" reset
	@goose -dir db/migrations postgres "$(DATABASE_URL)" up

# Database production
db-up-prod: ## Run pending migrations on production database
	@if [ -z "$(DATABASE_URL_PROD)" ]; then \
		echo "❌ Error: DATABASE_URL_PROD environment variable is required"; \
		exit 1; \
	fi
	@echo "⬆️  Running migrations on production database..."
	@goose -dir db/migrations postgres "$(DATABASE_URL_PROD)" up

db-status-prod: ## Show migration status on production database
	@if [ -z "$(DATABASE_URL_PROD)" ]; then \
		echo "❌ Error: DATABASE_URL_PROD environment variable is required"; \
		exit 1; \
	fi
	@echo "📊 Migration status on production database:"
	@goose -dir db/migrations postgres "$(DATABASE_URL_PROD)" status

db-down-prod: ## Rollback last migration on production database
	@if [ -z "$(DATABASE_URL_PROD)" ]; then \
		echo "❌ Error: DATABASE_URL_PROD environment variable is required"; \
		exit 1; \
	fi
	@echo "⬇️  Rolling back migration on production database..."
	@goose -dir db/migrations postgres "$(DATABASE_URL_PROD)" down

db-reset-prod: ## Reset production database (DOWN then UP)
	@if [ -z "$(DATABASE_URL_PROD)" ]; then \
		echo "❌ Error: DATABASE_URL_PROD environment variable is required"; \
		exit 1; \
	fi
	@echo "🔄 Resetting production database..."
	@goose -dir db/migrations postgres "$(DATABASE_URL_PROD)" reset
	@goose -dir db/migrations postgres "$(DATABASE_URL_PROD)" up

# =============================================================================
# Docker
# =============================================================================

docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	@docker build -t $(DOCKER_IMAGE):$(VERSION) -t $(DOCKER_IMAGE):latest .
	@echo "✅ Docker image built: $(DOCKER_IMAGE):$(VERSION)"

docker-run: ## Run bot in Docker container
	@echo "🐳 Running Docker container..."
	@docker run -d \
		--name music-bot \
		--env-file .env \
		-v $$(pwd)/playlist:/app/playlist \
		-v $$(pwd)/logs:/app/logs \
		$(DOCKER_IMAGE):latest
	@echo "✅ Container started: music-bot"

docker-stop: ## Stop and remove Docker container
	@echo "🛑 Stopping Docker container..."
	@docker stop music-bot || true
	@docker rm music-bot || true
	@echo "✅ Container stopped"

docker-logs: ## Show Docker container logs
	@docker logs -f music-bot

docker-shell: ## Open shell in running container
	@docker exec -it music-bot sh

# =============================================================================
# Docker Compose
# =============================================================================

compose-up: ## Start services with docker-compose
	@echo "🐳 Starting services..."
	@docker compose up -d
	@echo "✅ Services started"

compose-down: ## Stop services with docker-compose
	@echo "🛑 Stopping services..."
	@docker compose down
	@echo "✅ Services stopped"

compose-build: ## Build and start services with docker-compose
	@echo "🐳 Building and starting services..."
	@docker compose up -d --build
	@echo "✅ Services built and started"

compose-logs: ## Show docker-compose logs
	@docker compose logs -f

compose-restart: ## Restart services
	@echo "🔄 Restarting services..."
	@docker compose restart
	@echo "✅ Services restarted"

compose-ps: ## Show running services
	@docker compose ps

# =============================================================================
# Utility
# =============================================================================

setup: deps install ## Setup development environment
	@echo "✅ Development environment ready!"

check: fmt vet lint test ## Run all checks (fmt, vet, lint, test)
	@echo "✅ All checks passed!"

.PHONY: all
all: clean build ## Clean and build
	@echo "✅ Build complete!"