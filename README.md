# shanghai-re-agent

上海限定房地产 Agent MVP。它是给上海房地产公司内部经纪人和运营使用的 FastAPI Copilot，所有房源、政策、租赁、交易、营销和文档问答都限定在上海市行政区域内。

## 快速开始

```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY；没有 Key 时，规则测试和本地 smoke test 仍可运行

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

docker compose up -d db
python scripts/init_db.py
python scripts/seed_demo_data.py
python scripts/seed_shanghai_geo_data.py
python scripts/seed_demo_rental_listings.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 `http://localhost:8000/docs` 查看 API。
打开 `http://localhost:8000/map` 查看上海租房地图推荐页。

已有数据库从早期版本升级时，如曾创建过 `user_anchors.customer_id` 的 UUID 列，请在启动前执行：

```bash
python scripts/migrate_user_anchor_customer_id.py
```

## 核心 API

- `GET /health`
- `POST /api/chat`
- `POST /api/listings/search`
- `POST /api/policies/ingest`
- `POST /api/documents/upload`
- `POST /api/repair/triage`
- `POST /api/marketing/generate`
- `POST /api/geo/geocode`
- `POST /api/commute/estimate`
- `POST /api/rental/recommend`
- `POST /api/map/rental-recommendations`
- `POST /api/insights/social`
- `GET /map`

## 高德地图配置

`.env` 中可配置：

```env
AMAP_WEB_SERVICE_KEY=
AMAP_JS_API_KEY=
AMAP_JS_SECURITY_CODE=
AMAP_DEFAULT_CITY=上海
AMAP_DEFAULT_CITY_CODE=021
AMAP_CACHE_TTL_HOURS=168
AMAP_LIVE_CALL_CONCURRENCY=4
AMAP_ENABLE_LIVE=true
ENABLE_DEMO_RENTAL_DATA=true
```

没有 `AMAP_WEB_SERVICE_KEY` 或设置 `AMAP_ENABLE_LIVE=false` 时，后端不会调用高德 Web 服务，地理编码和路线会返回 `unavailable`，推荐 API 不会崩溃，也不会编造通勤时间。没有 `AMAP_JS_API_KEY` 时，`/map` 页面仍能显示表单和推荐列表，但不显示高德底图。

## 租房地图推荐模式

- `listing_mode`：已导入真实上海可租房源，推荐具体房源。
- `demo_listing_mode`：只有 demo 房源时用于演示算法，结果必须带 `is_demo=true` 和数据警示。
- `area_mode`：没有真实房源或不允许 demo 时，只推荐上海区域、地铁站和板块，不推荐具体房子。

示例：

```bash
curl -X POST http://localhost:8000/api/rental/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query":"我在张江上班，预算5500，想租一室户，通勤45分钟以内",
    "allow_demo_data": true,
    "commute_modes": ["transit"]
  }'
```

导入真实房源 CSV：

```bash
python scripts/import_rental_listings_csv.py /path/to/rental_listings.csv
```

CSV 最低字段参考 `data/demo/rental_listings_demo.csv`。所有真实房源必须 `city=上海`，坐标必须在上海范围内；脚本按 `external_id` 幂等更新。

## 示例请求

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我找浦东800万以内的三房"}'
```

```bash
curl -X POST http://localhost:8000/api/repair/triage \
  -H "Content-Type: application/json" \
  -d '{"description":"厨房有燃气异味，灶台附近味道很重"}'
```

## 测试

```bash
pytest
python scripts/smoke_test.py
```

## 业务红线

- 公司只服务上海。昆山、苏州、太仓、嘉善、杭州、南通、无锡等外地请求必须拒绝。
- 对外营销文案只允许使用 `verification_status='verified'` 且 `entrusted_status='active'` 的上海房源。
- 不承诺学区、入学、落户、贷款审批、涨价或收益。
- 不协助伪造社保、个税、流水、居住证、合同或房源核验码。
- 合同、税费、定金、产权、抵押、查封、户口等争议必须转人工。
- 燃气、电路、消防、严重漏水必须转人工，并提示安全动作。
- 政策回答必须基于本地 `policy_chunks` 或 `data/policies` 检索结果，没有来源时明确说明本地政策库不足。
