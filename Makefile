# ParkSmart AI — lệnh dành cho dev. Chạy từ gốc repo; code server nằm trong server/ (ADR-0001).
#
# Gõ `make` hoặc `make help` để xem bảng lệnh.
#   - Target có `## mô tả` ở cuối dòng sẽ hiện trong bảng.
#   - Dòng `##@ Tên nhóm` mở một nhóm mới.

.DEFAULT_GOAL := help

PYTHON  ?= python3
COMPOSE ?= docker compose

# ---------------------------------------------------------------------------
# Tham số dùng chung
# ---------------------------------------------------------------------------
# PROFILE  : profile compose thêm khi `make up` — app | workers | tools | all, nhiều cái cách bằng dấu phẩy
# SERVICE  : service cho logs / shell (mặc định api)
# INTERVAL : số giây chờ giữa hai container khi `make start` (mặc định 30)
# STRICT=1 : eval fail khi có regression
# NO_CACHE=1 : build lại image không dùng cache
# VOLUMES=1  : `make down` xoá luôn volume (MẤT dữ liệu Postgres/Redis local)
PROFILE  ?=
SERVICE  ?=
STRICT   ?=
NO_CACHE ?=
VOLUMES  ?=
INTERVAL ?= 30

comma := ,
ALL_PROFILES      := workers tools app seed
SELECTED_PROFILES := $(if $(filter all,$(PROFILE)),$(ALL_PROFILES),$(subst $(comma), ,$(PROFILE)))
PROFILE_FLAGS     := $(foreach p,$(SELECTED_PROFILES),--profile $(p))
# stop/down/ps/logs phải thấy mọi profile, nếu không container của profile sẽ bị bỏ sót.
ALL_PROFILE_FLAGS := $(foreach p,$(ALL_PROFILES),--profile $(p))

# Lệnh `make shell` mở theo từng service; service khác mở `sh`.
SHELL_CMD_postgres := psql -U parksmart -d parksmart
SHELL_CMD_redis    := redis-cli

.PHONY: help install run seed lint format typecheck test check eval \
        up start stop down build ps logs shell clean

##@ Chung

help: ## Hiện bảng lệnh này
	@awk 'BEGIN { FS = ":.*## "; \
		printf "\nCách dùng: make \033[36m<lệnh>\033[0m [THAM_SỐ=giá_trị]\n"; \
		printf "Tham số: PROFILE=app,workers,tools|all  SERVICE=api|postgres|redis|...  INTERVAL=30  STRICT=1  NO_CACHE=1  VOLUMES=1\n" } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5); \
			printf "  LỆNH         MÔ TẢ\n"; \
			printf "  %-12s %s\n", "------------", "------------------------------------------------------------"; next } \
		/^[a-zA-Z0-9_-]+:.*## / { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@printf "\n\033[1mVí dụ\033[0m\n"
	@printf "  \033[36m%-34s\033[0m %s\n" \
		"make up"                    "tạo container postgres + redis (chưa chạy)" \
		"make up PROFILE=tools"      "+ pgAdmin :5050, Redis Insight :5540" \
		"make up PROFILE=workers"    "+ worker, agent-worker (cần bật arq trong requirements.txt)" \
		"make up PROFILE=app"        "+ api :8000" \
		"make up PROFILE=all"        "+ app + tools + workers" \
		"make start"                 "start lần lượt container đã có, cách nhau 30s" \
		"make start INTERVAL=10"     "như trên, cách nhau 10s" \
		"make logs SERVICE=postgres" "xem log postgres" \
		"make shell SERVICE=redis"   "mở redis-cli" \
		"make down VOLUMES=1"        "xoá container + volume (MẤT dữ liệu local)"
	@echo ""

##@ Phát triển local (không Docker)

install: ## Cài thư viện backend (server/requirements.txt)
	pip install -r server/requirements.txt

run: ## Chạy API có reload tại http://localhost:8000/docs
	cd server && uvicorn app.main_api:app --app-dir src --reload --host 0.0.0.0 --port 8000

seed: ## Seed dữ liệu demo 3 khu vào DB trong .env (cần SEED_DEMO=true; DRY=1 chỉ in số liệu rồi rollback)
	$(PYTHON) server/scripts/seed_demo.py $(if $(DRY),--dry-run)

##@ Chất lượng code

lint: ## Kiểm tra lint bằng ruff
	cd server && ruff check src/ tests/

format: ## Format code bằng ruff
	cd server && ruff format src/ tests/

typecheck: ## Kiểm tra kiểu bằng mypy
	cd server && mypy src/

test: ## Chạy pytest
	cd server && pytest -v

# CI (.github/workflows/ci.yml) chỉ gọi `make check`: sửa bước kiểm tra ở đây, CI tự theo.
check: lint typecheck test ## Lint + typecheck + test — phải pass trước khi báo "xong"; CI chạy lệnh này trên mọi PR

eval: ## Chạy eval, ghi eval/results/report.md (không cần API key; STRICT=1 để fail khi regression)
	$(PYTHON) eval/run_eval.py $(if $(STRICT),--strict)

##@ Docker · Chạy và dừng

up: .env ## Tạo container postgres + redis ở trạng thái dừng (PROFILE=app | workers | tools | all để thêm); bật bằng `make start`
	$(COMPOSE) $(PROFILE_FLAGS) create --build
	@echo "Đã tạo container (đang dừng). Chạy \`make start\` để bật lần lượt."

stop: ## Dừng mọi container, giữ container và dữ liệu
	$(COMPOSE) $(ALL_PROFILE_FLAGS) stop

start: ## Start lần lượt các container đã có (đã tạo bằng `make up`), cách nhau INTERVAL giây (mặc định 30)
	$(PYTHON) scripts/compose_start.py --interval $(INTERVAL) $(ALL_PROFILE_FLAGS)

down: ## Xoá container, giữ volume DB (VOLUMES=1 xoá cả volume — MẤT dữ liệu local)
	$(COMPOSE) $(ALL_PROFILE_FLAGS) down $(if $(VOLUMES),-v)

##@ Docker · Build image

build: ## Build image server (NO_CACHE=1 để build lại từ đầu)
	$(COMPOSE) $(PROFILE_FLAGS) build $(if $(NO_CACHE),--no-cache)

##@ Docker · Theo dõi và truy cập

ps: ## Liệt kê container và trạng thái
	$(COMPOSE) $(ALL_PROFILE_FLAGS) ps

logs: ## Theo dõi log (mặc định api; SERVICE=postgres để đổi)
	$(COMPOSE) $(ALL_PROFILE_FLAGS) logs -f --tail=100 $(or $(SERVICE),api)

shell: ## Vào container: api → sh, postgres → psql, redis → redis-cli (SERVICE=..., mặc định api)
	$(COMPOSE) exec $(or $(SERVICE),api) $(or $(SHELL_CMD_$(or $(SERVICE),api)),sh)

##@ Dọn dẹp

clean: ## Xoá cache Python (__pycache__, .pytest_cache, .ruff_cache)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

# Tạo .env từ .env.example nếu chưa có (không có prerequisite nên không bao giờ ghi đè .env sẵn có).
.env:
	@$(PYTHON) -c "import shutil; shutil.copyfile('.env.example', '.env'); print('Đã tạo .env từ .env.example')"
