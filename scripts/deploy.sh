#!/bin/bash
set -euo pipefail

# ===========================================
# FastAPI Boilerplate - Deployment Script
# ===========================================
# This script handles the deployment process:
# 1. Pull the latest Docker image
# 2. Stop existing containers
# 3. Start new containers
# 4. Health check
# 5. Rollback on failure

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Configuration
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://127.0.0.1:8000/}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-60}"
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-5}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env_file() {
    if [[ ! -f ".env" ]]; then
        log_error ".env file not found!"
        log_error "Please create .env file with required environment variables."
        exit 1
    fi
    log_info ".env file found"
}

# Pull the latest Docker image
pull_image() {
    log_info "Pulling latest Docker image..."
    docker compose -f "$COMPOSE_FILE" pull app || {
        log_warn "Failed to pull image, will use local build"
    }
}

# Backup current state for rollback
backup_state() {
    log_info "Creating backup of current deployment state..."
    if docker compose -f "$COMPOSE_FILE" ps -q app 2>/dev/null | grep -q .; then
        BACKUP_IMAGE=$(docker compose -f "$COMPOSE_FILE" images app -q 2>/dev/null || echo "")
        if [[ -n "$BACKUP_IMAGE" ]]; then
            docker tag "$BACKUP_IMAGE" fastapi-boilerplate:rollback 2>/dev/null || true
            log_info "Backup image tagged as fastapi-boilerplate:rollback"
        fi
    else
        log_info "No existing deployment found, skipping backup"
    fi
}

# Stop existing containers
stop_containers() {
    log_info "Stopping existing containers..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
}

# Start new containers
start_containers() {
    log_info "Starting new containers..."
    docker compose -f "$COMPOSE_FILE" up -d
}

# Health check
health_check() {
    log_info "Running health check..."
    local elapsed=0
    
    while [[ $elapsed -lt $HEALTH_CHECK_TIMEOUT ]]; do
        local http_code
        http_code=$(curl -sS -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL" 2>/dev/null || echo "000")
        
        if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
            log_info "Health check passed!"
            return 0
        fi
        
        log_info "Waiting for application to be ready... (${elapsed}s/${HEALTH_CHECK_TIMEOUT}s)"
        sleep "$HEALTH_CHECK_INTERVAL"
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
    done
    
    log_error "Health check failed after ${HEALTH_CHECK_TIMEOUT}s"
    return 1
}

# Rollback to previous version
rollback() {
    log_error "Deployment failed! Initiating rollback..."
    
    if docker image inspect fastapi-boilerplate:rollback > /dev/null 2>&1; then
        log_info "Rolling back to previous version..."
        docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
        
        # Use rollback image
        DOCKER_IMAGE=fastapi-boilerplate:rollback docker compose -f "$COMPOSE_FILE" up -d
        
        if health_check; then
            log_info "Rollback successful!"
        else
            log_error "Rollback also failed! Manual intervention required."
            exit 1
        fi
    else
        log_error "No rollback image available. Manual intervention required."
        exit 1
    fi
}

# Cleanup old images
cleanup() {
    log_info "Cleaning up old Docker images..."
    docker image prune -f || true
}

# Main deployment process
main() {
    log_info "=========================================="
    log_info "Starting deployment..."
    log_info "=========================================="
    
    check_env_file
    pull_image
    backup_state
    stop_containers
    start_containers
    
    if health_check; then
        log_info "=========================================="
        log_info "Deployment completed successfully!"
        log_info "=========================================="
        cleanup
    else
        rollback
    fi
}

# Run main function
main "$@"
