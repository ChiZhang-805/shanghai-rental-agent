# 上海房地产公司 Agent 本地落地方案（WSL2 Ubuntu 22.04）

> 适用目标：先在本地 WSL2 Ubuntu 环境做一个可运行的上海限定房地产 Agent MVP，后续再扩展成企业微信 / 微信小程序 / Web 工作台。  
> 约束：公司只服务上海；所有房源检索、政策问答、租赁/买卖流程、维修工单均限定为上海业务。  
> 技术基线：Python + FastAPI + PostgreSQL/pgvector + OpenAI API + 本地文件存储。  
> 实现策略：先做“内部经纪人/运营 Copilot”，不是直接面向公众的自动成交机器人。

---

## 1. 目标产物

本地 MVP 交付一个仓库：`shanghai-re-agent`。

实现后你应能在 WSL2 里运行：

```bash
cp .env.example .env
# 填入 OPENAI_API_KEY

docker compose up -d db
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/init_db.py
python scripts/seed_demo_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

然后访问：

```text
http://localhost:8000/docs
```

核心 API：

```text
GET  /health
POST /api/chat
POST /api/listings/search
POST /api/policies/ingest
POST /api/documents/upload
POST /api/repair/triage
POST /api/marketing/generate
```

第一版不要做复杂前端。用 FastAPI Swagger + 一个 CLI 聊天脚本验证即可。

---

## 2. MVP 功能边界

### 2.1 必须实现

| 模块 | 说明 | OpenAI API 使用点 |
|---|---|---|
| 上海范围守门器 | 检查请求、房源、政策、输出是否限定上海 | 不一定调用 LLM，先用确定性规则 |
| 总控 Supervisor Agent | 判断用户意图并路由到专业 Agent | Responses API + Structured Outputs |
| 客户需求 Agent | 从聊天中抽取预算、区域、通勤、户型、买/租意图 | Responses API + Structured Outputs |
| 房源推荐 Agent | 上海房源筛选、排序、解释推荐理由 | Embeddings API + Responses API |
| 政策 Agent | 上海政策 RAG 问答，必须带来源 | Embeddings API + Responses API |
| 租赁 Agent | 房源核验、网签备案材料、合同条款解释、租赁风险提示 | Responses API + Policy Agent |
| 交易流程 Agent | 买卖交易材料清单、时间线、待确认事项 | Responses API + Policy Agent |
| 维修 Agent | 文字/图片维修问题分类、紧急程度、工单生成 | Vision input + Responses API |
| 营销文案 Agent | 生成房源文案，并经过合规检查 | Responses API |
| 合规 Agent | 输出前审查：学区承诺、虚假房源、外地房源、伪造材料等 | 规则引擎 + Responses API |
| 文档 Agent | 对合同、委托书、产证材料做摘要/问答 | Embeddings API + Responses API |

### 2.2 暂不实现

| 暂不做 | 原因 |
|---|---|
| 自动提交网签备案 | 涉及官方系统、身份认证、企业授权 |
| 自动判断最终购房资格 | 必须以交易中心、银行、公积金中心等核验为准 |
| 自动法律意见 | 高风险，应转人工或律师 |
| 自动税费最终计算 | 上海政策和个案复杂，MVP 只做材料清单和初步提示 |
| 面向公众全自动客服 | 先做内部 Copilot，便于人工审核 |
| 未授权爬取第三方平台房源 | 法务与数据授权风险高 |

---

## 3. 本地技术栈

### 3.1 后端

```text
Python 3.10+ / 3.11
FastAPI
Uvicorn
Pydantic v2
SQLAlchemy 2.x
Alembic
psycopg[binary]
pgvector
openai Python SDK
python-dotenv / pydantic-settings
tenacity
orjson
python-multipart
Pillow
```

### 3.2 数据层

```text
PostgreSQL 16 + pgvector
本地 uploads/ 文件夹保存图片和文档
```

第一版不强依赖 Redis、MinIO、Neo4j、PostGIS。后续生产化再上。

### 3.3 为什么第一版用 pgvector，而不是 Milvus/Chroma

- 本地 WSL2 部署更简单；
- 结构化房源筛选和向量检索在同一个数据库内完成；
- 房地产 Agent 的第一性问题是“结构化过滤 + 上海范围约束”，不是单纯语义检索；
- 后续数据量上来后可迁移到 Milvus/Qdrant。

---

## 4. WSL2 环境准备

> 用户提到 Ubuntu 22.02，实际常见版本是 Ubuntu 22.04。下面按 22.04 写。

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  curl \
  git \
  make \
  python3 \
  python3-venv \
  python3-pip \
  libpq-dev \
  docker.io \
  docker-compose-plugin

sudo usermod -aG docker $USER
# 退出并重新进入 WSL，使 docker 用户组生效
```

验证：

```bash
docker --version
docker compose version
python3 --version
```

创建项目：

```bash
mkdir -p ~/projects
cd ~/projects
git init shanghai-re-agent
cd shanghai-re-agent
```

---

## 5. 仓库结构

Codex 应按下面结构生成文件：

```text
shanghai-re-agent/
  README.md
  AGENTS.md
  .env.example
  .gitignore
  docker-compose.yml
  pyproject.toml
  alembic.ini
  app/
    __init__.py
    main.py
    config.py
    db.py
    logging_config.py
    models/
      __init__.py
      base.py
      listing.py
      customer.py
      policy.py
      document.py
      repair.py
      transaction.py
      chat.py
      audit.py
    schemas/
      __init__.py
      common.py
      chat.py
      listings.py
      customer_need.py
      policy.py
      repair.py
      marketing.py
      compliance.py
      transaction.py
      documents.py
    services/
      __init__.py
      openai_service.py
      embedding_service.py
      retrieval_service.py
      listing_service.py
      policy_service.py
      document_service.py
      image_service.py
      compliance_service.py
      city_guard.py
      audit_service.py
    agents/
      __init__.py
      base.py
      supervisor.py
      customer_need_agent.py
      listing_agent.py
      policy_agent.py
      rental_agent.py
      transaction_agent.py
      repair_agent.py
      marketing_agent.py
      document_agent.py
      compliance_agent.py
    api/
      __init__.py
      deps.py
      routes/
        __init__.py
        health.py
        chat.py
        listings.py
        policies.py
        documents.py
        repair.py
        marketing.py
    prompts/
      supervisor.md
      customer_need.md
      listing_explainer.md
      policy_qa.md
      rental.md
      transaction.md
      repair.md
      marketing.md
      compliance.md
      document_qa.md
    scripts/
      init_db.py
      seed_demo_data.py
      ingest_policies.py
      embed_all.py
      chat_cli.py
      smoke_test.py
    data/
      policies/
        shanghai_rental_contract_filing_2024.md
        shanghai_rental_regulation_2023.md
        shanghai_listing_verification_2023.md
        shanghai_practitioner_realname_2023.md
      demo/
        listings.csv
        customers.csv
    tests/
      test_city_guard.py
      test_customer_need_agent.py
      test_listing_search.py
      test_policy_agent.py
      test_compliance_agent.py
      test_repair_agent.py
```

---

## 6. 环境变量

`.env.example`：

```env
APP_ENV=local
APP_NAME=shanghai-re-agent
LOG_LEVEL=INFO

# OpenAI
OPENAI_API_KEY=
OPENAI_RESPONSES_MODEL=gpt-5.5
OPENAI_VISION_MODEL=gpt-5.5
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIM=1536
OPENAI_REQUEST_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=3

# Database
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent_password
POSTGRES_DB=shanghai_re_agent
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://agent:agent_password@localhost:5432/shanghai_re_agent

# Local files
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=20

# Business constraints
SHANGHAI_ONLY=true
ALLOW_PUBLIC_OUTPUT=false
REQUIRE_HUMAN_REVIEW_FOR_MARKETING=true
REQUIRE_VERIFIED_LISTING_FOR_MARKETING=true

# Retrieval
POLICY_TOP_K=6
LISTING_TOP_K=10
DOCUMENT_TOP_K=6
VECTOR_SIMILARITY_THRESHOLD=0.25
```

安全规则：

```text
永远不要把 OPENAI_API_KEY 写进代码、日志、测试快照、README 示例输出。
只从环境变量读取。
本地 .env 必须加入 .gitignore。
```

---

## 7. docker-compose.yml

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: shanghai_re_agent_db
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: agent_password
      POSTGRES_DB: shanghai_re_agent
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d shanghai_re_agent"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  pgdata:
```

数据库初始化时必须执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 8. pyproject.toml

```toml
[project]
name = "shanghai-re-agent"
version = "0.1.0"
description = "Shanghai-only real estate agent MVP"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "sqlalchemy>=2.0.0",
  "alembic>=1.13.0",
  "psycopg[binary]>=3.2.0",
  "pgvector>=0.3.0",
  "openai>=1.0.0",
  "python-dotenv>=1.0.0",
  "python-multipart>=0.0.9",
  "pillow>=10.0.0",
  "tenacity>=8.5.0",
  "orjson>=3.10.0",
  "rich>=13.7.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "httpx>=0.27.0",
  "ruff>=0.5.0",
  "mypy>=1.10.0"
]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

---

## 9. 核心数据模型

### 9.1 上海行政区枚举

`app/schemas/common.py`：

```python
SHANGHAI_DISTRICTS = [
    "黄浦", "徐汇", "长宁", "静安", "普陀", "虹口", "杨浦",
    "闵行", "宝山", "嘉定", "浦东", "金山", "松江", "青浦",
    "奉贤", "崇明",
]

OUTSIDE_SHANGHAI_CITY_KEYWORDS = [
    "昆山", "苏州", "太仓", "嘉善", "嘉兴", "杭州", "南通", "无锡",
    "南京", "北京", "深圳", "广州", "成都", "武汉", "杭州湾",
]
```

### 9.2 Listing

必须带 `city` 且默认只能是 `上海`。

```python
class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_code: Mapped[str] = mapped_column(unique=True, index=True)
    city: Mapped[str] = mapped_column(default="上海", index=True)
    district: Mapped[str] = mapped_column(index=True)
    subdistrict: Mapped[str | None]
    community_name: Mapped[str] = mapped_column(index=True)
    address_masked: Mapped[str | None]
    lat: Mapped[float | None]
    lon: Mapped[float | None]

    purpose: Mapped[str]  # sale | rent
    property_type: Mapped[str]  # residential | apartment | office | retail
    title: Mapped[str]
    description: Mapped[str | None]
    rooms: Mapped[int | None]
    halls: Mapped[int | None]
    bathrooms: Mapped[int | None]
    area_sqm: Mapped[float]
    floor: Mapped[str | None]
    total_floors: Mapped[int | None]
    orientation: Mapped[str | None]
    decoration: Mapped[str | None]
    built_year: Mapped[int | None]
    has_elevator: Mapped[bool | None]

    sale_price_total: Mapped[int | None]  # 元
    rent_price_monthly: Mapped[int | None]  # 元/月

    verification_code: Mapped[str | None]
    verification_status: Mapped[str]  # verified | pending | missing | expired
    entrusted_status: Mapped[str]  # active | expired | missing
    listing_status: Mapped[str]  # active | inactive | sold | rented

    source: Mapped[str] = mapped_column(default="internal")
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

必须有数据库约束或应用层校验：

```text
city == "上海"
district in SHANGHAI_DISTRICTS
```

### 9.3 ListingEmbedding

```python
class ListingEmbedding(Base):
    __tablename__ = "listing_embeddings"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    text_hash: Mapped[str]
    updated_at: Mapped[datetime]
```

Embedding 文本拼接规则：

```text
title + community_name + district + subdistrict + rooms + area + price + decoration + description
```

### 9.4 PolicyDocument / PolicyChunk

```python
class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    source_url: Mapped[str]
    source_org: Mapped[str]  # 上海市房屋管理局 / 上海市人民政府 / 上海市住房租赁公共服务平台等
    published_at: Mapped[date | None]
    effective_from: Mapped[date | None]
    effective_to: Mapped[date | None]
    doc_type: Mapped[str]  # rental | sale | broker | verification | tax | general
    is_active: Mapped[bool] = mapped_column(default=True)
    raw_text: Mapped[str]
    created_at: Mapped[datetime]

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id"))
    chunk_index: Mapped[int]
    chunk_text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
```

### 9.5 Customer / CustomerNeed

```python
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None]
    phone_masked: Mapped[str | None]
    role: Mapped[str]  # buyer | seller | tenant | landlord | unknown
    assigned_agent_id: Mapped[int | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

class CustomerNeed(Base):
    __tablename__ = "customer_needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    purpose: Mapped[str]  # buy | rent | sell | lease_out | unknown
    districts: Mapped[dict]  # JSON array
    budget_total_min: Mapped[int | None]
    budget_total_max: Mapped[int | None]
    rent_budget_min: Mapped[int | None]
    rent_budget_max: Mapped[int | None]
    rooms_min: Mapped[int | None]
    rooms_max: Mapped[int | None]
    area_min: Mapped[float | None]
    area_max: Mapped[float | None]
    commute_to: Mapped[str | None]
    commute_limit_minutes: Mapped[int | None]
    family_stage: Mapped[str | None]
    must_haves: Mapped[dict]
    nice_to_haves: Mapped[dict]
    missing_fields: Mapped[dict]
    risk_flags: Mapped[dict]
    updated_at: Mapped[datetime]
```

### 9.6 RepairTicket

```python
class RepairTicket(Base):
    __tablename__ = "repair_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    issue_type: Mapped[str]  # plumbing | electricity | gas | appliance | mold | lock | other
    severity: Mapped[str]  # low | medium | high | emergency
    description: Mapped[str]
    image_paths: Mapped[dict]
    safety_instructions: Mapped[dict]
    status: Mapped[str]  # created | assigned | in_progress | done | cancelled
    needs_human: Mapped[bool]
    created_at: Mapped[datetime]
```

### 9.7 AgentAuditLog

所有 Agent 调用都写日志，但不要记录 API Key。

```python
class AgentAuditLog(Base):
    __tablename__ = "agent_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str]
    agent_name: Mapped[str]
    input_summary: Mapped[str]
    output_summary: Mapped[str]
    model: Mapped[str | None]
    token_usage: Mapped[dict | None]
    risk_level: Mapped[str]
    needs_human: Mapped[bool]
    created_at: Mapped[datetime]
```

---

## 10. OpenAI API 服务层设计

### 10.1 统一入口

`app/services/openai_service.py` 必须封装所有 OpenAI 调用，不允许业务 Agent 到处直接 `OpenAI()`。

```python
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

class OpenAIService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.default_model = settings.openai_responses_model
        self.embedding_model = settings.openai_embedding_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def text(self, system: str, user: str, model: str | None = None) -> str:
        response = self.client.responses.create(
            model=model or self.default_model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.output_text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def json_response(self, system: str, user: str, schema_name: str, schema: dict, model: str | None = None) -> dict:
        response = self.client.responses.create(
            model=model or self.default_model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        # MVP：用 json.loads(response.output_text)。后续可改用 SDK parse helper。
        return safe_json_loads(response.output_text)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
```

### 10.2 图片分析

维修 Agent 需要接收本地图片，所以采用 Base64 data URL。

```python
import base64
import mimetypes

class OpenAIService:
    def vision_json(self, prompt: str, image_path: str, schema_name: str, schema: dict) -> dict:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.responses.create(
            model=settings.openai_vision_model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                ],
            }],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        return safe_json_loads(response.output_text)
```

### 10.3 OpenAI API 在本项目中的调用点

| 调用点 | 文件 | 用途 |
|---|---|---|
| `responses.create` | `openai_service.text` | 普通回答、解释、文案生成 |
| `responses.create` + `text.format.json_schema` | `openai_service.json_response` | 路由、需求抽取、合规检查、维修分类、结构化输出 |
| `embeddings.create` | `embedding_service.py` | 政策、房源、文档向量化 |
| `responses.create` + `input_image` | `openai_service.vision_json` | 维修图片识别、房源图片问题初筛 |
| 可选 `moderations.create` | `compliance_service.py` | 公共输入/输出安全检查 |
| 可选 OpenAI Vector Stores | `policy_service.py` | 后续托管式 file_search，不作为本地 MVP 必需项 |

---

## 11. 上海范围守门器 CityGuard

`app/services/city_guard.py`

### 11.1 目标

任何 Agent 之前和之后都要过 CityGuard：

1. 用户请求是否涉及非上海房源；
2. 检索条件是否被强制限定为上海；
3. 返回的 listing 是否均为上海；
4. 输出是否暗示公司可服务上海以外城市。

### 11.2 实现函数

```python
class CityGuard:
    def normalize_districts(self, text: str) -> list[str]: ...

    def detect_outside_shanghai(self, text: str) -> list[str]: ...

    def assert_request_allowed(self, text: str) -> CityGuardResult:
        # 如果用户问“昆山房子也可以吗”“苏州推荐房源”，返回 allowed=False
        # 如果用户问“上海周边通勤到上海”，也必须返回 allowed=False 或提示仅服务上海市行政区内。

    def force_listing_filters(self, filters: ListingSearchFilters) -> ListingSearchFilters:
        filters.city = "上海"
        return filters

    def validate_listing_rows(self, listings: list[Listing]) -> None:
        for listing in listings:
            assert listing.city == "上海"
            assert listing.district in SHANGHAI_DISTRICTS
```

### 11.3 默认拒绝话术

```text
XXX 公司目前只服务上海市行政区域内的房产。你提到的地点不属于上海业务范围，我不能推荐或分析外地房源。可以继续帮你筛选上海的房源、租赁备案、交易材料或维修问题。
```

### 11.4 单元测试

```python
def test_reject_kunshan():
    result = CityGuard().assert_request_allowed("帮我推荐昆山花桥的房子")
    assert result.allowed is False


def test_accept_pudong():
    result = CityGuard().assert_request_allowed("我想看浦东张江附近两房")
    assert result.allowed is True
```

---

## 12. Agent 总体编排

### 12.1 Agent 列表

| Agent | 作用 | 是否直接调用 OpenAI | 是否可调用其他 Agent |
|---|---|---:|---:|
| SupervisorAgent | 意图识别、路由、最终聚合 | 是 | 是 |
| CustomerNeedAgent | 需求抽取、画像更新 | 是 | 否 |
| ListingAgent | 房源搜索、推荐解释 | 是 | 可调用 CustomerNeedAgent、ComplianceAgent |
| PolicyAgent | 上海政策 RAG | 是 | 否 |
| RentalAgent | 租赁流程与备案助手 | 是 | PolicyAgent、ListingAgent |
| TransactionAgent | 买卖流程、材料清单、时间线 | 是 | PolicyAgent |
| RepairAgent | 维修分类、工单生成、图片识别 | 是 | ComplianceAgent |
| MarketingAgent | 文案生成 | 是 | ListingAgent、ComplianceAgent |
| DocumentAgent | 合同/委托/材料问答 | 是 | PolicyAgent、ComplianceAgent |
| ComplianceAgent | 风险审查、人工接管 | 是 | 否 |

### 12.2 统一响应格式

所有 Agent 返回 `AgentResponse`：

```python
class Source(BaseModel):
    title: str
    source_url: str | None = None
    chunk_id: str | None = None
    published_at: str | None = None

class Action(BaseModel):
    type: Literal["ask_user", "create_task", "handoff", "show_listing", "create_ticket"]
    label: str
    payload: dict = Field(default_factory=dict)

class AgentResponse(BaseModel):
    answer: str
    agent_name: str
    intent: str
    data: dict = Field(default_factory=dict)
    sources: list[Source] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    needs_human: bool = False
    confidence: float = 0.0
```

### 12.3 总流程

```text
/api/chat
  ↓
CityGuard.assert_request_allowed(user_message)
  ↓
ComplianceAgent.check_input(user_message)
  ↓
SupervisorAgent.route(user_message)
  ↓
对应专业 Agent.run()
  ↓
ComplianceAgent.check_output(agent_response)
  ↓
CityGuard.validate_output(agent_response)
  ↓
AuditLog 写入
  ↓
返回 AgentResponse
```

---

## 13. SupervisorAgent 具体实现

`app/agents/supervisor.py`

### 13.1 输入

```python
class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: int | None = None
    role: Literal["agent", "manager", "customer", "operator"] = "agent"
    message: str
    image_paths: list[str] = Field(default_factory=list)
    listing_id: int | None = None
    customer_id: int | None = None
```

### 13.2 路由输出 Schema

```python
ROUTE_SCHEMA = {
  "type": "object",
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "listing_search", "policy_qa", "rental_flow", "transaction_flow",
        "repair_triage", "marketing_copy", "document_qa", "customer_need_update",
        "smalltalk", "human_handoff", "out_of_scope"
      ]
    },
    "confidence": {"type": "number"},
    "reason": {"type": "string"},
    "requires_image": {"type": "boolean"},
    "requires_listing": {"type": "boolean"},
    "requires_policy_sources": {"type": "boolean"},
    "risk_flags": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["intent", "confidence", "reason", "requires_image", "requires_listing", "requires_policy_sources", "risk_flags"],
  "additionalProperties": False
}
```

### 13.3 路由规则

确定性优先，LLM 辅助：

| 关键词/条件 | 路由 |
|---|---|
| “推荐房”“找房”“预算”“几房”“地铁”“通勤” | `listing_search` |
| “限购”“社保”“个税”“房产税”“公积金”“政策” | `policy_qa` |
| “租赁备案”“租房合同”“押金”“退租”“房源核验码” | `rental_flow` |
| “买卖流程”“网签”“过户”“贷款材料”“交易进度” | `transaction_flow` |
| 上传图片且提到漏水/燃气/电/门锁/发霉 | `repair_triage` |
| “写文案”“朋友圈”“小红书”“标题” | `marketing_copy` |
| 上传合同/委托书/产证材料并提问 | `document_qa` |
| 非上海城市 | `out_of_scope` |
| 要求伪造材料、规避监管 | `human_handoff` |

### 13.4 Supervisor Prompt

`app/prompts/supervisor.md`：

```text
你是 XXX 上海房地产公司的总控路由 Agent。公司只服务上海市行政区域内房产业务。

任务：根据用户输入判断最合适的专业 Agent。

硬性规则：
1. 涉及上海以外城市或房源推荐，intent 必须是 out_of_scope。
2. 涉及伪造社保、个税、流水、居住证、合同、核验码，intent 必须是 human_handoff，并加入 risk_flags。
3. 涉及燃气、电路、消防、严重漏水、人身安全，优先 repair_triage，并加入 risk_flags。
4. 涉及政策、购房资格、备案、网签，必须要求来源。
5. 不得输出面向用户的最终答案，只输出结构化路由 JSON。
```

### 13.5 `run()` 伪代码

```python
class SupervisorAgent:
    def run(self, request: ChatRequest) -> AgentResponse:
        guard_result = city_guard.assert_request_allowed(request.message)
        if not guard_result.allowed:
            return out_of_scope_response(guard_result)

        route = openai_service.json_response(
            system=load_prompt("supervisor.md"),
            user=request.message,
            schema_name="route_decision",
            schema=ROUTE_SCHEMA,
        )

        agent = self.agent_registry[route["intent"]]
        response = agent.run(request)
        checked = compliance_agent.check_output(response)
        city_guard.validate_agent_response(checked)
        return checked
```

---

## 14. CustomerNeedAgent 具体实现

`app/agents/customer_need_agent.py`

### 14.1 作用

把自然语言转为结构化客户画像，并写入 `customer_needs`。

### 14.2 输出 Schema

```python
CUSTOMER_NEED_SCHEMA = {
  "type": "object",
  "properties": {
    "purpose": {"type": "string", "enum": ["buy", "rent", "sell", "lease_out", "unknown"]},
    "districts": {"type": "array", "items": {"type": "string"}},
    "budget_total_min": {"type": ["integer", "null"]},
    "budget_total_max": {"type": ["integer", "null"]},
    "rent_budget_min": {"type": ["integer", "null"]},
    "rent_budget_max": {"type": ["integer", "null"]},
    "rooms_min": {"type": ["integer", "null"]},
    "rooms_max": {"type": ["integer", "null"]},
    "area_min": {"type": ["number", "null"]},
    "area_max": {"type": ["number", "null"]},
    "commute_to": {"type": ["string", "null"]},
    "commute_limit_minutes": {"type": ["integer", "null"]},
    "family_stage": {"type": ["string", "null"]},
    "must_haves": {"type": "array", "items": {"type": "string"}},
    "nice_to_haves": {"type": "array", "items": {"type": "string"}},
    "missing_questions": {"type": "array", "items": {"type": "string"}},
    "risk_flags": {"type": "array", "items": {"type": "string"}}
  },
  "required": [
    "purpose", "districts", "budget_total_min", "budget_total_max", "rent_budget_min", "rent_budget_max",
    "rooms_min", "rooms_max", "area_min", "area_max", "commute_to", "commute_limit_minutes",
    "family_stage", "must_haves", "nice_to_haves", "missing_questions", "risk_flags"
  ],
  "additionalProperties": False
}
```

### 14.3 Prompt

`app/prompts/customer_need.md`：

```text
你是上海房地产客户需求抽取 Agent。请从用户输入中抽取结构化买房、租房、卖房或出租需求。

硬性规则：
1. 城市只能是上海。若用户提到上海以外城市，把该城市放入 risk_flags，不要放入 districts。
2. districts 只能使用上海行政区简称：黄浦、徐汇、长宁、静安、普陀、虹口、杨浦、闵行、宝山、嘉定、浦东、金山、松江、青浦、奉贤、崇明。
3. 预算单位统一为人民币元。用户说“800万”，输出 8000000。
4. 租金预算统一为元/月。
5. 不要承诺学区、落户、贷款、涨价。
6. 如果缺关键字段，加入 missing_questions。
7. 只输出 JSON，不要输出解释。
```

### 14.4 实现步骤

```text
1. CityGuard 检查输入。
2. 调用 OpenAI Structured Outputs 抽取需求。
3. 清洗 districts，丢弃非上海地名。
4. 如果 customer_id 存在，合并旧画像：新输入覆盖明确字段，旧字段保留。
5. 写入 customer_needs。
6. 返回摘要和缺失问题。
```

### 14.5 示例

输入：

```text
我在张江上班，预算 800 万，想买两房，通勤 45 分钟内，不要太老。
```

输出：

```json
{
  "purpose": "buy",
  "districts": ["浦东"],
  "budget_total_min": null,
  "budget_total_max": 8000000,
  "rent_budget_min": null,
  "rent_budget_max": null,
  "rooms_min": 2,
  "rooms_max": 2,
  "area_min": null,
  "area_max": null,
  "commute_to": "张江",
  "commute_limit_minutes": 45,
  "family_stage": null,
  "must_haves": ["两房", "通勤45分钟内", "楼龄不要太老"],
  "nice_to_haves": [],
  "missing_questions": ["是否已有上海购房资格初筛信息？", "首付和贷款计划是否已确认？"],
  "risk_flags": ["购房资格需人工核验"]
}
```

---

## 15. ListingAgent 具体实现

`app/agents/listing_agent.py`

### 15.1 作用

只在上海房源库中检索并推荐房源。LLM 不得编造房源事实。

### 15.2 输入

```python
class ListingSearchRequest(BaseModel):
    purpose: Literal["buy", "rent"]
    districts: list[str] = []
    budget_total_max: int | None = None
    rent_budget_max: int | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    area_min: float | None = None
    area_max: float | None = None
    commute_to: str | None = None
    commute_limit_minutes: int | None = None
    free_text: str | None = None
    require_verified: bool = True
    top_k: int = 10
```

### 15.3 检索策略

必须按下面顺序做：

```text
1. CityGuard.force_listing_filters：city 固定为 上海。
2. SQL 硬过滤：
   - city = '上海'
   - listing_status = 'active'
   - purpose = sale/rent
   - district in 上海行政区
   - 价格/租金 <= 用户预算上限
   - 房间数、面积等硬条件
   - 对外营销场景 require_verified=true 时，verification_status='verified'
3. 向量检索：
   - 如果 free_text 存在，调用 OpenAI Embeddings API 获取 query embedding。
   - 用 pgvector 找相似 listing。
4. 规则打分：
   - 硬条件匹配分
   - 预算贴合度
   - 房间数/面积贴合度
   - 核验状态加分
   - 委托状态加分
   - 向量相似度
5. 取 top_k。
6. LLM 只负责把已有字段整理成推荐理由，不得新增事实。
7. ComplianceAgent 检查输出。
```

### 15.4 SQL 过滤示例

```python
query = select(Listing).where(
    Listing.city == "上海",
    Listing.listing_status == "active",
)

if request.purpose == "buy":
    query = query.where(Listing.purpose == "sale")
    if request.budget_total_max:
        query = query.where(Listing.sale_price_total <= request.budget_total_max)

if request.purpose == "rent":
    query = query.where(Listing.purpose == "rent")
    if request.rent_budget_max:
        query = query.where(Listing.rent_price_monthly <= request.rent_budget_max)

if request.districts:
    query = query.where(Listing.district.in_(request.districts))

if request.require_verified:
    query = query.where(Listing.verification_status == "verified")
```

### 15.5 推荐解释 Prompt

`app/prompts/listing_explainer.md`：

```text
你是上海房地产经纪人 Copilot 的房源推荐解释 Agent。

你只能基于输入 JSON 中已有的房源字段和客户需求生成解释。

硬性规则：
1. 不得编造房源不存在的字段、地铁距离、学校、成交记录、税费、产权状态。
2. 不得承诺学区、入学、落户、涨价、贷款审批。
3. 每个推荐必须包含：匹配点、待确认项、风险提示。
4. 房源必须是上海，若发现非上海房源，直接输出 risk_flags 并要求人工检查。
5. 对缺少核验码或委托状态异常的房源，不得建议对外发布。
```

### 15.6 输出

```python
class ListingRecommendation(BaseModel):
    listing_id: int
    listing_code: str
    title: str
    district: str
    community_name: str
    price_text: str
    match_score: float
    match_reasons: list[str]
    missing_confirmations: list[str]
    risk_flags: list[str]
```

---

## 16. PolicyAgent 具体实现

`app/agents/policy_agent.py`

### 16.1 作用

回答上海房产政策问题，只基于本地已入库的官方政策文档。不得凭空说“最新政策”。

### 16.2 首批政策库

把下面 4 类资料整理成 Markdown 放到 `data/policies/`，每个文件顶部用 YAML front matter：

```yaml
---
title: "关于印发《上海市住房租赁合同网签备案操作规定》的通知"
source_org: "上海市房屋管理局"
source_url: "https://fgj.sh.gov.cn/gfxwj/20241111/d1b199d4e18543d094a6808226e3e4e1.html"
published_at: "2024-11-11"
effective_from: "2024-12-01"
effective_to: "2029-06-30"
doc_type: "rental_filing"
---
```

首批文件：

```text
1. 上海市住房租赁合同网签备案操作规定
2. 上海市住房租赁条例
3. 上海市住房租赁公共服务平台管理规定 / 房源核验相关规则
4. 上海住房租赁和房地产经纪行业从业人员实名从业通知
```

### 16.3 RAG 流程

```text
1. 用户问题 -> Embeddings API 生成 query vector。
2. pgvector 搜索 policy_chunks top_k=6。
3. 关键词补召回：如果问题包含“核验码/备案/从业信息卡/群租/阳台/厨房”，优先补对应 doc_type。
4. 过滤 inactive 或过期政策。
5. 把检索 chunks 连同 title/source_url/published_at/effective_from 输入 LLM。
6. LLM 输出结构化 PolicyAnswer。
7. 如果检索不到来源，回答“本地政策库暂无足够依据，需要补充官方政策源”，不能胡答。
```

### 16.4 输出 Schema

```python
POLICY_ANSWER_SCHEMA = {
  "type": "object",
  "properties": {
    "answer": {"type": "string"},
    "applies_to_shanghai_only": {"type": "boolean"},
    "policy_basis": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "source_url": {"type": "string"},
          "published_at": {"type": ["string", "null"]},
          "effective_from": {"type": ["string", "null"]},
          "quote_or_summary": {"type": "string"}
        },
        "required": ["title", "source_url", "published_at", "effective_from", "quote_or_summary"],
        "additionalProperties": False
      }
    },
    "required_user_info": {"type": "array", "items": {"type": "string"}},
    "next_steps": {"type": "array", "items": {"type": "string"}},
    "disclaimer": {"type": "string"},
    "needs_human": {"type": "boolean"},
    "risk_flags": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["answer", "applies_to_shanghai_only", "policy_basis", "required_user_info", "next_steps", "disclaimer", "needs_human", "risk_flags"],
  "additionalProperties": False
}
```

### 16.5 Prompt

`app/prompts/policy_qa.md`：

```text
你是 XXX 上海房地产公司的上海政策问答 Agent。你只能基于提供的检索片段回答。

硬性规则：
1. 只回答上海市行政区域内房产业务相关问题。
2. 不得使用常识或训练记忆补充政策内容。
3. 每个结论都必须对应至少一个 policy_basis。
4. 如果片段不足，明确说“本地政策库不足，需补充官方来源或人工确认”。
5. 不得给最终法律、税务、贷款审批结论。
6. 涉及购房资格、税费、公积金、网签备案，应提醒最终以主管部门、交易中心、银行、公积金中心等审核为准。
7. 输出必须是 JSON。
```

### 16.6 政策库入库脚本

`scripts/ingest_policies.py`：

```text
1. 遍历 data/policies/*.md。
2. 解析 YAML front matter。
3. 按 800-1200 中文字符切块，chunk_overlap 100-150 字。
4. 调用 OpenAI Embeddings API 生成向量。
5. 写入 policy_documents 和 policy_chunks。
6. 重复运行时按 source_url + title upsert。
```

---

## 17. RentalAgent 具体实现

`app/agents/rental_agent.py`

### 17.1 覆盖场景

```text
租房咨询
出租咨询
房源核验码检查
租赁合同条款解释
网签备案材料清单
押金/租金/退租交接提醒
群租/非居住空间出租风险识别
```

### 17.2 输入意图细分

用 Structured Outputs 细分：

```python
RENTAL_INTENT_SCHEMA = {
  "type": "object",
  "properties": {
    "rental_intent": {
      "type": "string",
      "enum": [
        "find_rental", "lease_out", "filing_checklist", "contract_explain",
        "deposit_dispute", "move_out", "verification_code", "illegal_group_rent", "unknown"
      ]
    },
    "needs_policy": {"type": "boolean"},
    "needs_listing": {"type": "boolean"},
    "needs_human": {"type": "boolean"},
    "risk_flags": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["rental_intent", "needs_policy", "needs_listing", "needs_human", "risk_flags"],
  "additionalProperties": False
}
```

### 17.3 实现逻辑

```text
if rental_intent == find_rental:
    调 CustomerNeedAgent + ListingAgent，仅返回上海租赁房源。

if rental_intent == verification_code:
    如果 listing_id 存在，查 verification_status 和 verification_code。
    如果缺失，输出“不建议对外发布/需补齐核验”。

if rental_intent == filing_checklist:
    调 PolicyAgent 查询“住房租赁合同网签备案”。
    输出材料清单、办理渠道、待确认项。

if rental_intent == contract_explain:
    调 DocumentAgent 或直接对用户提供的条款做解释。
    输出“条款含义、风险点、需人工确认”。

if rental_intent == illegal_group_rent:
    调 PolicyAgent 查询群租/非居住空间出租规定。
    needs_human=True。
```

### 17.4 Prompt

`app/prompts/rental.md`：

```text
你是上海住房租赁业务 Agent，服务对象是房地产公司的经纪人、管家和运营人员。

硬性规则：
1. 只处理上海住房租赁业务。
2. 房源发布前必须提示核验码或核验状态。
3. 不得建议发布未核验、委托缺失、已出租、已下架房源。
4. 涉及网签备案、群租、非居住空间出租，必须调用/引用政策 Agent 的来源。
5. 涉及合同争议，只能做条款解释和材料清单，不作法律结论。
6. 输出必须包含：结论、依据、下一步动作、人工确认项。
```

---

## 18. TransactionAgent 具体实现

`app/agents/transaction_agent.py`

### 18.1 覆盖场景

```text
买房材料清单
卖房材料清单
购房资格初筛问题清单
贷款/公积金材料提醒
二手房交易时间线
网签/过户/交房节点
交易风险提示
```

### 18.2 P0 不做什么

```text
不输出“你一定有资格买房”。
不输出“银行一定能批贷”。
不输出最终税费精算。
不替代交易中心、银行、公积金中心、税务、律师意见。
```

### 18.3 工具函数

```python
def build_buyer_readiness_questions(customer_need: CustomerNeed | None) -> list[str]:
    return [
        "是否为上海户籍？",
        "家庭名下上海住房套数？",
        "婚姻状态及家庭成员情况？",
        "非沪籍是否满足社保/个税等要求？",
        "首付资金来源是否已确认？",
        "是否计划商业贷款或公积金贷款？",
    ]


def build_second_hand_transaction_timeline() -> list[dict]:
    return [
        {"stage": "需求和资格初筛", "owner": "经纪人/客户", "human_review": True},
        {"stage": "看房与意向确认", "owner": "经纪人", "human_review": False},
        {"stage": "产权和抵押等状态核查", "owner": "经纪人/交易专员", "human_review": True},
        {"stage": "签约及网签材料准备", "owner": "交易专员", "human_review": True},
        {"stage": "贷款/公积金资料准备", "owner": "客户/银行", "human_review": True},
        {"stage": "过户与缴税", "owner": "交易专员/客户", "human_review": True},
        {"stage": "交房与物业水电燃气交接", "owner": "经纪人/客户", "human_review": False},
    ]
```

### 18.4 Prompt

`app/prompts/transaction.md`：

```text
你是上海二手房/租赁交易流程 Copilot。

硬性规则：
1. 只服务上海。
2. 只输出流程、材料清单、待确认事项、风险提示。
3. 不给最终购房资格、贷款审批、税费法律结论。
4. 涉及政策依据时必须调用 PolicyAgent 检索来源。
5. 涉及产权、抵押、查封、户口、租约、定金、税费争议，needs_human=true。
6. 输出必须适合经纪人内部使用。
```

---

## 19. RepairAgent 具体实现

`app/agents/repair_agent.py`

### 19.1 覆盖场景

```text
漏水
墙面发霉
电路跳闸
燃气异味
门锁损坏
家电故障
窗户/门损坏
下水堵塞
消防/安全隐患
```

### 19.2 输出 Schema

```python
REPAIR_TRIAGE_SCHEMA = {
  "type": "object",
  "properties": {
    "issue_type": {
      "type": "string",
      "enum": ["plumbing", "electricity", "gas", "appliance", "mold", "lock", "window", "structure", "fire_safety", "other"]
    },
    "severity": {"type": "string", "enum": ["low", "medium", "high", "emergency"]},
    "summary": {"type": "string"},
    "visible_evidence": {"type": "array", "items": {"type": "string"}},
    "immediate_actions": {"type": "array", "items": {"type": "string"}},
    "questions_to_ask": {"type": "array", "items": {"type": "string"}},
    "ticket_title": {"type": "string"},
    "ticket_description": {"type": "string"},
    "needs_human": {"type": "boolean"},
    "risk_flags": {"type": "array", "items": {"type": "string"}}
  },
  "required": [
    "issue_type", "severity", "summary", "visible_evidence", "immediate_actions",
    "questions_to_ask", "ticket_title", "ticket_description", "needs_human", "risk_flags"
  ],
  "additionalProperties": False
}
```

### 19.3 紧急程度规则

| 条件 | severity | 动作 |
|---|---|---|
| 燃气味、燃气设备异常 | emergency | 立即人工、提示开窗、勿开关电器、联系物业/燃气 |
| 明火、冒烟、消防隐患 | emergency | 立即人工、建议拨打紧急电话/物业 |
| 大面积漏水、影响楼下 | high | 关闭阀门、通知物业和管家 |
| 电路跳闸、插座冒火花 | high/emergency | 停止使用、人工介入 |
| 墙面发霉 | medium | 拍照、通风、安排检查 |
| 普通家电故障 | low/medium | 创建工单 |

### 19.4 Prompt

`app/prompts/repair.md`：

```text
你是上海租赁/物业维修 Agent。根据用户文字和图片判断维修类型、紧急程度和下一步动作。

硬性规则：
1. 不要诊断医学问题。
2. 不要指导用户自行维修燃气、电路、消防等高风险问题。
3. 燃气、电路、消防、严重漏水必须 needs_human=true。
4. 如果图片无法判断，明确提出需要补拍或补充信息。
5. 输出必须是结构化 JSON。
6. 用于生成工单，不用于替代专业维修人员判断。
```

### 19.5 实现步骤

```text
1. 接收 message 和图片文件。
2. 如果有图片，调用 OpenAI vision_json。
3. 如果无图片，调用 OpenAI json_response。
4. 根据确定性紧急规则二次覆盖 severity。
5. 创建 RepairTicket。
6. 返回安全提示、工单号、是否人工介入。
```

---

## 20. MarketingAgent 具体实现

`app/agents/marketing_agent.py`

### 20.1 作用

为上海房源生成经纪人内部审核用文案。

支持：

```text
朋友圈
小红书
公众号短文
视频号口播脚本
房源标题
带看话术
```

### 20.2 输入

```python
class MarketingRequest(BaseModel):
    listing_id: int
    channel: Literal["wechat_moments", "xiaohongshu", "official_account", "video_script", "title", "showing_script"]
    tone: Literal["professional", "warm", "concise", "premium"] = "professional"
    extra_requirements: str | None = None
```

### 20.3 处理流程

```text
1. 查 listing。
2. CityGuard.validate_listing_rows。
3. 如果 listing.city != 上海，拒绝。
4. 如果 REQUIRE_VERIFIED_LISTING_FOR_MARKETING=true 且 verification_status != verified，拒绝。
5. 如果 entrusted_status != active，提示不可对外发布。
6. 构造 facts JSON，只给 LLM 已核实字段。
7. LLM 生成草稿。
8. ComplianceAgent 检查并改写。
9. 返回 draft + compliance_report + requires_human_review=true。
```

### 20.4 禁止词和风险模式

```text
稳赚
必涨
抄底
无风险
保证落户
保证上岸
包上某学校
学区房承诺
内部价
独家真实但无委托
不限购
可做假流水
可包装资质
```

### 20.5 Prompt

`app/prompts/marketing.md`：

```text
你是上海房地产公司的房源营销文案 Agent。你只能根据提供的房源 facts 写文案。

硬性规则：
1. 不得编造面积、价格、地铁距离、学校、税费、产权、核验、成交记录。
2. 不得承诺涨价、收益、落户、入学、贷款审批。
3. 不得制造恐慌或诱导非理性交易。
4. 不得使用歧视性客户筛选表述。
5. 如果 facts 中没有字段，就不能写。
6. 输出要包含：标题、正文、事实依据字段、人工审核提醒。
```

---

## 21. ComplianceAgent 具体实现

`app/agents/compliance_agent.py`

### 21.1 作用

所有输入和输出都要经过 ComplianceAgent。

### 21.2 两阶段设计

#### 阶段一：确定性规则

```python
BLOCK_PATTERNS = {
    "forgery": ["伪造", "做假", "假社保", "假个税", "假流水", "包装资质", "代办假"],
    "outside_shanghai": OUTSIDE_SHANGHAI_CITY_KEYWORDS,
    "school_promise": ["包上", "保证入学", "一定能进", "学区名额"],
    "investment_promise": ["稳赚", "必涨", "无风险", "保底收益"],
    "unverified_listing": ["没核验也发", "没有委托也发", "虚假房源"],
    "illegal_rental": ["阳台出租", "厨房出租", "卫生间出租", "隔断群租"],
}
```

#### 阶段二：OpenAI 结构化审查

```python
COMPLIANCE_SCHEMA = {
  "type": "object",
  "properties": {
    "allowed": {"type": "boolean"},
    "risk_level": {"type": "string", "enum": ["none", "low", "medium", "high", "blocked"]},
    "needs_human": {"type": "boolean"},
    "violations": {"type": "array", "items": {"type": "string"}},
    "safe_rewrite": {"type": ["string", "null"]},
    "reason": {"type": "string"}
  },
  "required": ["allowed", "risk_level", "needs_human", "violations", "safe_rewrite", "reason"],
  "additionalProperties": False
}
```

### 21.3 Prompt

`app/prompts/compliance.md`：

```text
你是上海房地产公司内部合规审查 Agent。检查输入或输出是否存在房产业务风险。

重点风险：
1. 上海以外房源推荐或暗示公司服务外地。
2. 伪造社保、个税、流水、居住证、合同、核验码。
3. 未核验房源发布、虚假房源、委托缺失仍营销。
4. 学区、入学、落户、贷款、涨价、收益保证。
5. 群租、非居住空间出租、违规隔断。
6. 合同争议、定金纠纷、税费争议、法律结论。
7. 燃气、电路、消防、严重漏水等安全问题未转人工。
8. 过度收集或泄露个人敏感信息。

输出 JSON。若存在 high/blocked 风险，needs_human 必须为 true。
```

### 21.4 输出处理

```text
allowed=false：拒绝并返回安全话术。
risk_level=high：返回初步说明 + needs_human=true。
risk_level=medium：允许返回，但必须附风险提示。
safe_rewrite 不为空：用 safe_rewrite 替换原文。
```

---

## 22. DocumentAgent 具体实现

`app/agents/document_agent.py`

### 22.1 支持文档

```text
租赁合同
买卖合同草稿
委托书
产证材料说明
维修记录
交割清单
房源描述文件
```

### 22.2 MVP 实现

第一版只处理 `.txt`, `.md`, `.pdf`。PDF 文本抽取可用 `pypdf`，扫描件 OCR 先不做或使用 OpenAI 文件/图片能力作为后续增强。

### 22.3 入库流程

```text
1. 上传文件到 uploads/documents/。
2. 抽取文本。
3. 按 800-1200 字切块。
4. 调 Embeddings API。
5. 写 document_chunks。
6. /api/chat 里如果用户指定 document_id，DocumentAgent 检索 top_k chunks。
7. LLM 基于 chunks 回答。
8. 涉及法律/争议结论，ComplianceAgent 标记 needs_human=true。
```

### 22.4 Prompt

`app/prompts/document_qa.md`：

```text
你是上海房地产公司内部文档问答 Agent。你只能根据提供的文档片段回答。

硬性规则：
1. 不得编造文档没有的信息。
2. 不得输出最终法律意见。
3. 对合同风险只能提示“需人工/法务确认”。
4. 涉及上海政策时调用 PolicyAgent。
5. 输出必须列出依据片段编号。
```

---

## 23. API 设计

### 23.1 POST /api/chat

请求：

```json
{
  "session_id": "s1",
  "role": "agent",
  "customer_id": 1,
  "listing_id": null,
  "message": "我客户预算800万，在张江上班，想买两房，通勤45分钟内",
  "image_paths": []
}
```

响应：

```json
{
  "answer": "已提取客户需求，并筛出 3 套上海房源。需要补充购房资格和首付贷款信息。",
  "agent_name": "ListingAgent",
  "intent": "listing_search",
  "data": {
    "recommendations": []
  },
  "sources": [],
  "actions": [
    {"type": "ask_user", "label": "补充购房资格信息", "payload": {}}
  ],
  "risk_flags": ["购房资格需人工核验"],
  "needs_human": false,
  "confidence": 0.86
}
```

### 23.2 POST /api/listings/search

直接房源搜索，不走完整聊天。

### 23.3 POST /api/repair/triage

使用 multipart：

```text
message: 厨房水槽下面漏水，地板泡了
listing_id: 1
customer_id: 1
files: image/jpeg
```

返回 RepairTicket。

### 23.4 POST /api/marketing/generate

请求：

```json
{
  "listing_id": 1,
  "channel": "xiaohongshu",
  "tone": "concise",
  "extra_requirements": "突出通勤和装修，但不要夸张"
}
```

返回：

```json
{
  "draft": "...",
  "compliance_report": {...},
  "requires_human_review": true
}
```

---

## 24. 种子数据

### 24.1 `data/demo/listings.csv`

至少 8 条上海房源：

```csv
listing_code,city,district,subdistrict,community_name,purpose,property_type,title,rooms,halls,bathrooms,area_sqm,sale_price_total,rent_price_monthly,decoration,built_year,has_elevator,verification_code,verification_status,entrusted_status,listing_status,description
SH-SALE-001,上海,浦东,张江,张江示例花园,sale,residential,张江两房近产业园,2,1,1,78,7800000,,精装,2012,true,HY001,verified,active,active,适合张江通勤客户，房源信息为演示数据
SH-SALE-002,上海,徐汇,徐家汇,徐汇示例公寓,sale,residential,徐汇成熟商圈两房,2,1,1,72,8200000,,简装,2005,true,HY002,verified,active,active,近商业配套，房源信息为演示数据
SH-RENT-001,上海,静安,大宁,大宁示例小区,rent,residential,静安大宁一房出租,1,1,1,52,,7800,精装,2016,true,HY003,verified,active,active,适合通勤租客，房源信息为演示数据
```

### 24.2 政策种子数据

先手工放 4 个 Markdown 摘要，不要把整篇法规大段复制。每个文件保留：

```text
标题
官方来源 URL
发布日期/生效日期
核心条款摘要
对 Agent 的业务规则
```

---

## 25. 运行脚本

### 25.1 初始化数据库

`scripts/init_db.py`：

```python
from sqlalchemy import text
from app.db import engine
from app.models import Base

with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

Base.metadata.create_all(bind=engine)
print("Database initialized")
```

### 25.2 种子数据

`scripts/seed_demo_data.py`：

```text
1. 读 data/demo/listings.csv。
2. upsert listings。
3. 调 EmbeddingService 为每个 listing 生成 embedding。
4. 写 listing_embeddings。
5. 调 ingest_policies.py。
```

### 25.3 CLI 聊天

`scripts/chat_cli.py`：

```bash
python scripts/chat_cli.py
> 我客户预算800万，在张江上班，想买两房
```

脚本内部调用：

```python
POST http://localhost:8000/api/chat
```

---

## 26. 测试要求

### 26.1 必须有的测试

```text
test_city_guard.py
- 昆山/苏州/杭州请求被拒绝
- 浦东/静安/徐汇请求通过
- listing.city != 上海 会抛出错误

test_customer_need_agent.py
- “800万”转成 8000000
- “张江上班”识别 commute_to
- “昆山也可以”进入 risk_flags

test_listing_search.py
- 所有结果 city 都是上海
- 未核验房源不会用于 marketing
- 预算过滤有效

test_policy_agent.py
- 政策回答必须有 sources
- 检索不到来源时不得胡答

test_compliance_agent.py
- 伪造社保被 blocked
- 包上学校被 high risk
- 未核验房源营销被 blocked

test_repair_agent.py
- 燃气异味 -> emergency + needs_human
- 普通门锁问题 -> medium/low
```

### 26.2 smoke_test

`scripts/smoke_test.py` 应依次验证：

```text
1. /health 返回 ok。
2. /api/chat 能提取买房需求。
3. /api/listings/search 返回上海房源。
4. /api/chat 问“上海租赁备案怎么办”能返回政策来源。
5. /api/chat 问“推荐昆山房子”被拒绝。
6. /api/marketing/generate 对 verified listing 生成需人工审核文案。
```

---

## 27. 人工接管规则

任何 Agent 如果遇到以下情况，必须 `needs_human=true`：

```text
伪造材料
规避限购/贷款/税费监管
外地房源推荐
未核验房源对外发布
群租/非居住空间出租
合同争议、定金争议、税务争议
产权、抵押、查封、户口迁移等交易风险
燃气、电路、消防、严重漏水
客户投诉或威胁
用户要求删除/导出/修改个人敏感信息
```

返回格式：

```json
{
  "needs_human": true,
  "risk_flags": ["合同争议需人工处理"],
  "actions": [
    {"type": "handoff", "label": "转交易专员/法务/店长处理", "payload": {"priority": "high"}}
  ]
}
```

---

## 28. 个人信息与日志

### 28.1 本地 MVP 也要做的事

```text
1. 手机号只存 masked：138****1234。
2. 身份证、社保、个税、婚姻、收入等敏感字段不要在 MVP 中落库。
3. AgentAuditLog 只记录摘要，不记录完整隐私材料。
4. 上传文档默认 private。
5. .env、uploads/、logs/ 加入 .gitignore。
```

### 28.2 `.gitignore`

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
uploads/
logs/
*.sqlite3
.DS_Store
```

---

## 29. 参考资料和设计依据

### OpenAI 官方文档

```text
OpenAI API Quickstart
https://developers.openai.com/api/docs/quickstart

OpenAI Agents SDK
https://developers.openai.com/api/docs/guides/agents

OpenAI Function Calling
https://developers.openai.com/api/docs/guides/function-calling

OpenAI Structured Outputs
https://developers.openai.com/api/docs/guides/structured-outputs

OpenAI Embeddings
https://developers.openai.com/api/docs/guides/embeddings

OpenAI Retrieval / Vector Stores
https://developers.openai.com/api/docs/guides/retrieval

OpenAI Images and Vision
https://developers.openai.com/api/docs/guides/images-vision
```

### 上海官方/准官方政策源

```text
上海市住房租赁合同网签备案操作规定
https://fgj.sh.gov.cn/gfxwj/20241111/d1b199d4e18543d094a6808226e3e4e1.html

上海市住房租赁条例
https://www.shanghai.gov.cn/bzxzlzfjbzcsjzc/20230418/8a0798aa5f444182a33065910f5b272c.html

上海市住房租赁公共服务平台管理规定相关文件
https://fgj.sh.gov.cn/

上海市房屋管理局关于进一步做好本市住房租赁和房地产经纪行业从业人员实名从业的工作通知
https://fgj.sh.gov.cn/fdcsc/20231227/5fa5005eedbf417cae05398065976322.html
```

---

## 30. 发给 Codex 的实现 Prompt

把下面整段发给 Codex：

```text
你是一个资深 Python/FastAPI/LLM 工程师。请在当前仓库实现一个“上海限定房地产 Agent MVP”。要求按以下约束完成代码、配置、脚本和测试。

【项目目标】
实现一个可在 WSL2 Ubuntu 22.04 本地运行的 FastAPI 服务，项目名 shanghai-re-agent。该服务是上海房地产公司的内部经纪人/运营 Copilot，只服务上海市行政区域内的房产业务。MVP 包括：总控路由 Agent、上海范围守门器、客户需求抽取 Agent、房源推荐 Agent、政策 RAG Agent、租赁 Agent、交易流程 Agent、维修图片/文字 Agent、营销文案 Agent、文档问答 Agent、合规 Agent。

【强制业务规则】
1. 公司只服务上海。任何房源搜索、推荐、政策问答、租赁/买卖流程、营销文案都必须限定 city='上海'。
2. 如果用户要求推荐或分析上海以外城市，如昆山、苏州、太仓、嘉善、杭州、南通、无锡等，必须拒绝，并说明公司只服务上海。
3. 对外营销文案必须要求房源 verification_status='verified' 且 entrusted_status='active'。
4. 不得承诺学区、入学、落户、贷款审批、涨价、收益。
5. 不得帮助伪造社保、个税、流水、居住证、合同、房源核验码。
6. 涉及合同争议、税费争议、定金争议、产权/抵押/查封/户口等问题，必须 needs_human=true。
7. 涉及燃气、电路、消防、严重漏水，必须 needs_human=true 并给安全提示。
8. 政策回答必须基于本地 policy_chunks 检索结果；没有来源不得胡答。

【技术要求】
1. 使用 Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2.x、PostgreSQL 16 + pgvector、OpenAI Python SDK。
2. 所有 OpenAI 调用集中在 app/services/openai_service.py，不允许在 Agent 文件里直接创建 OpenAI client。
3. OpenAI API Key 只从环境变量 OPENAI_API_KEY 读取；不要写死，不要输出到日志。
4. 使用 Responses API 进行文本生成和结构化输出；使用 text.format json_schema 严格输出 JSON。
5. 使用 OpenAI Embeddings API 为房源、政策、文档生成向量，默认模型 text-embedding-3-small，维度 1536。
6. 维修图片分析使用 Responses API 的 input_image，图片从本地文件转为 base64 data URL。
7. 所有函数应有类型标注。关键路径写单元测试。

【请创建以下文件结构】
- README.md
- AGENTS.md
- .env.example
- .gitignore
- docker-compose.yml
- pyproject.toml
- app/main.py
- app/config.py
- app/db.py
- app/models/*
- app/schemas/*
- app/services/openai_service.py
- app/services/embedding_service.py
- app/services/retrieval_service.py
- app/services/listing_service.py
- app/services/policy_service.py
- app/services/document_service.py
- app/services/image_service.py
- app/services/compliance_service.py
- app/services/city_guard.py
- app/agents/supervisor.py
- app/agents/customer_need_agent.py
- app/agents/listing_agent.py
- app/agents/policy_agent.py
- app/agents/rental_agent.py
- app/agents/transaction_agent.py
- app/agents/repair_agent.py
- app/agents/marketing_agent.py
- app/agents/document_agent.py
- app/agents/compliance_agent.py
- app/api/routes/health.py
- app/api/routes/chat.py
- app/api/routes/listings.py
- app/api/routes/policies.py
- app/api/routes/documents.py
- app/api/routes/repair.py
- app/api/routes/marketing.py
- app/prompts/*.md
- scripts/init_db.py
- scripts/seed_demo_data.py
- scripts/ingest_policies.py
- scripts/embed_all.py
- scripts/chat_cli.py
- scripts/smoke_test.py
- data/demo/listings.csv
- data/policies/*.md
- tests/*.py

【数据库模型】
实现以下表：listings、listing_embeddings、policy_documents、policy_chunks、customers、customer_needs、documents、document_chunks、repair_tickets、chat_messages、agent_audit_logs。listings 必须有 city、district、purpose、price、verification_status、entrusted_status、listing_status 等字段。listing_embeddings 和 policy_chunks 使用 pgvector Vector(1536)。

【Agent 具体要求】
1. CityGuard：实现 normalize_districts、detect_outside_shanghai、assert_request_allowed、force_listing_filters、validate_listing_rows。非上海请求必须拒绝。
2. ComplianceAgent：先规则检查，再用 OpenAI Structured Outputs 输出 allowed、risk_level、needs_human、violations、safe_rewrite、reason。检查伪造材料、外地房源、学区承诺、收益承诺、未核验房源营销、群租、法律/税务争议、安全风险、隐私风险。
3. SupervisorAgent：用 OpenAI Structured Outputs 输出 intent，枚举包括 listing_search、policy_qa、rental_flow、transaction_flow、repair_triage、marketing_copy、document_qa、customer_need_update、smalltalk、human_handoff、out_of_scope。根据 intent 调用专业 Agent。
4. CustomerNeedAgent：把中文自然语言抽取为结构化需求，预算单位统一为元，“800万”要转 8000000，districts 只能是上海行政区。
5. ListingAgent：先 SQL 过滤 city='上海'，再用 pgvector 语义检索，最后用规则打分。LLM 只负责基于已有字段解释推荐理由，不能编造事实。
6. PolicyAgent：读取 data/policies 的官方政策摘要，切块、向量化、检索。回答必须带 policy_basis；检索不到来源时明确说本地政策库不足。
7. RentalAgent：处理找租房、出租、房源核验码、租赁备案材料清单、合同条款解释、押金退租、群租风险。涉及法规时调用 PolicyAgent。
8. TransactionAgent：输出上海买卖交易流程、材料清单、购房资格初筛问题清单、交易时间线。不得给最终资格/贷款/税费结论。
9. RepairAgent：支持文字和图片，输出 issue_type、severity、summary、immediate_actions、questions_to_ask、ticket_title、ticket_description、needs_human、risk_flags，并创建 repair_tickets。
10. MarketingAgent：基于 listing facts 生成朋友圈/小红书/公众号/视频号/标题/带看话术。未核验或委托异常房源不得生成对外文案。输出必须 requires_human_review=true。
11. DocumentAgent：支持上传 txt/md/pdf，抽取文本、切块、嵌入、检索问答。不能输出法律结论。

【API】
实现：
- GET /health
- POST /api/chat
- POST /api/listings/search
- POST /api/policies/ingest
- POST /api/documents/upload
- POST /api/repair/triage
- POST /api/marketing/generate

【种子数据】
创建 data/demo/listings.csv，至少包含 8 条上海房源，覆盖 sale/rent、浦东/徐汇/静安/闵行等区，包含 verified 和 missing verification 两类状态。创建 data/policies 下 4 个政策摘要 Markdown，带 YAML front matter：title、source_org、source_url、published_at、effective_from、effective_to、doc_type。

【测试】
实现 pytest：
- 昆山/苏州请求被 CityGuard 拒绝；浦东/静安通过。
- 客户需求抽取能把 800万 转成 8000000。
- ListingAgent 返回的所有 listing.city 都是 上海。
- MarketingAgent 对未核验房源拒绝生成对外文案。
- PolicyAgent 在无来源时不得胡答；有来源时返回 policy_basis。
- ComplianceAgent 阻断伪造社保、包上学校、稳赚等。
- RepairAgent 对燃气异味输出 emergency + needs_human=true。

【交付标准】
1. `docker compose up -d db` 可启动数据库。
2. `python scripts/init_db.py` 可初始化表和 pgvector extension。
3. `python scripts/seed_demo_data.py` 可写入房源、政策并生成 embedding。
4. `uvicorn app.main:app --reload` 可启动。
5. `python scripts/smoke_test.py` 全部通过。
6. `pytest` 通过。
7. README 写清楚安装、配置 OPENAI_API_KEY、启动、测试、示例请求。

请直接实现代码。不要只写方案。不要把 OPENAI_API_KEY 写死。不要引入前端。优先保证后端 MVP 可运行、测试可过、Agent 逻辑清晰。
```

---

## 31. 实施顺序建议

让 Codex 一次性实现可能比较大。更稳的拆分顺序：

```text
第 1 轮：项目骨架 + 配置 + DB + models + /health。
第 2 轮：CityGuard + ComplianceAgent + 测试。
第 3 轮：OpenAIService + CustomerNeedAgent + SupervisorAgent。
第 4 轮：ListingAgent + seed_demo_data + pgvector embedding。
第 5 轮：PolicyAgent + ingest_policies。
第 6 轮：RentalAgent + TransactionAgent。
第 7 轮：RepairAgent 图片/文字 triage。
第 8 轮：MarketingAgent + DocumentAgent。
第 9 轮：smoke_test + README + 清理。
```

本地先把第 1-5 轮做通，就已经是可演示的上海房产 Agent MVP。
