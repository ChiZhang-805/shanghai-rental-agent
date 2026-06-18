# 上海租房 Agent 增量优化方案：地图可视化 + 高德通勤评分 + 房源数据接入层

> 本文档是在上一版 `shanghai-re-agent` 本地 MVP 方案基础上的增量优化。目标是在 WSL2 Ubuntu 22.04 本地可运行版本里，补上“租房地图可视化、通勤路线自动计算、通勤纳入选房评分、缺少真实租房平台数据时的降级方案、未来平台/公司房源数据接入层”。

---

## 0. 这次优化的核心判断

你提出的方向可以做，而且应该优先做。原因是：

1. **租房决策天然是地理决策**：预算、通勤、地铁、商圈、楼龄、维修风险、生活配套共同决定体验。
2. **没有真实房源平台数据时，也可以先做“区域/小区/地铁站候选推荐”**：本地 MVP 不应假装知道真实可租房源。先用 demo 数据和候选区域做算法闭环。
3. **具体租哪一套房，需要真实库存数据**：来自公司内部房源库、授权租房平台 API、平台导出表、经纪人手工录入、CRM/ERP。没有这些数据，只能推荐“适合找房的区域/小区/站点”，不能承诺某套房真实可租。
4. **高德地图适合做路线、地理编码、地图展示**：后端用 Web 服务 API 做地理编码和路线规划；前端用 JS API 2.0 做地图、Marker、Polyline、信息窗体。
5. **OpenAI API 适合做自然语言需求抽取、图片/笔记观点提取、推荐解释、权重推断、合规审查**：真正的打分和路线计算必须用确定性代码和高德结果，不能让 LLM 猜通勤时间。

---

## 1. 增量目标

在上一版仓库基础上新增以下能力：

```text
用户输入：
  我在张江上班，预算 5500，想租一室户，最多通勤 45 分钟，最好地铁方便。

系统输出：
  1. 结构化需求：预算、工作地点、通勤阈值、出行方式、偏好权重。
  2. 高德地理编码：把“张江”转成上海内坐标。
  3. 候选房源/候选区域：从本地 demo 房源或真实房源库里筛选。
  4. 高德路径规划：计算每个候选点到工作地点的公交/骑行/驾车/步行耗时。
  5. 综合评分：预算 + 通勤 + 地铁距离 + 配套 + 风险。
  6. 地图可视化：Marker 展示推荐点，点击后展示评分、租金、通勤路线、推荐理由。
  7. 数据警示：如果是 demo 数据，明确标注“非真实可租房源”。
```

---

## 2. 数据现实：没有租房平台数据时怎么做

### 2.1 必须区分两种推荐模式

| 模式 | 数据来源 | 能否推荐具体房子 | 适用阶段 |
|---|---|---:|---|
| `area_mode` 区域模式 | 小区/地铁站/板块 demo 数据、手工维护数据、高德地理数据 | 不能，只推荐区域、站点、小区方向 | 当前本地 MVP |
| `listing_mode` 房源模式 | 公司内部真实房源、授权平台 API、平台导出表、经纪人录入 | 可以，但要标注数据来源和更新时间 | 后续接入数据后 |
| `demo_listing_mode` 样例房源模式 | seed 脚本生成的假数据 | 不能用于真实租房，只用于演示算法 | 当前本地 MVP |

### 2.2 具体租哪套房，需要哪些字段

以后接入真实租房数据时，最低字段如下：

```csv
external_id,source,title,city,district,subdistrict,community_name,address,lng,lat,coordinate_system,
rent_monthly,deposit_months,payment_cycle,rooms,halls,bathrooms,area_sqm,floor,total_floors,
orientation,decoration,has_elevator,nearby_metro_station,metro_distance_m,
available_from,status,last_seen_at,listing_url,contact_name,contact_phone,is_verified,is_demo
```

字段说明：

| 字段 | 必要性 | 说明 |
|---|---:|---|
| `city` | 必须 | 必须等于“上海” |
| `lng/lat` | 强烈建议 | 没有坐标就要先 geocode，误差会变大 |
| `coordinate_system` | 必须 | 高德地图使用 GCJ-02 坐标；外部 WGS84 数据后续需要转换 |
| `rent_monthly` | 必须 | 月租金，用于预算评分 |
| `status` | 必须 | `available/offline/rented/unknown` |
| `last_seen_at` | 必须 | 判断房源时效 |
| `is_verified` | 建议 | 标记是否经过公司或平台核验 |
| `is_demo` | 必须 | demo 数据必须显式标记 |

### 2.3 不建议第一版爬链家/贝壳/自如/小红书

第一版不要把未经授权的爬虫作为生产数据源。原因：

- 平台服务条款和反爬策略有法律/合规风险；
- 页面数据字段不稳定；
- 房源真实性、价格时效、出租状态无法保证；
- 一旦 Agent 对外推荐“已失效/不存在”的房源，会直接损害公司信用。

正确做法：

```text
第一步：seed demo 数据，跑通算法和地图。
第二步：支持 CSV 导入真实房源。
第三步：对接公司内部房源库。
第四步：如有平台授权，再做 PlatformAdapter。
```

---

## 3. 高德地图接入设计

### 3.1 Key 配置

在 `.env.example` 中新增：

```bash
# AMap Web Service API：后端调用，不能暴露给前端
AMAP_WEB_SERVICE_KEY=

# AMap JS API：前端地图展示；本地开发可直接注入，生产建议走代理或域名白名单
AMAP_JS_API_KEY=
AMAP_JS_SECURITY_CODE=

# 上海限定配置
AMAP_DEFAULT_CITY=上海
AMAP_DEFAULT_CITY_CODE=021
AMAP_CACHE_TTL_HOURS=168
AMAP_LIVE_CALL_CONCURRENCY=4
AMAP_ENABLE_LIVE=true

# 本地 demo 模式
ENABLE_DEMO_RENTAL_DATA=true
```

高德 Web 服务 API 需要申请 Key，并把 Key 作为必填参数发送；地理编码 API 服务地址是 `https://restapi.amap.com/v3/geocode/geo`。高德路径规划 2.0 支持驾车、公交、步行、骑行、电动车等路线规划能力；其中驾车、步行、骑行、公交的 v5 服务地址分别为 `/v5/direction/driving`、`/v5/direction/walking`、`/v5/direction/bicycling`、`/v5/direction/transit/integrated`。高德 JS API 2.0 的新 Key 需要配合安全密钥使用；本地开发可以明文方式设置，生产建议通过代理服务器转发或做域名/服务端控制。

参考资料：

- 高德 Web 服务概述：https://amap.apifox.cn/
- 高德地理/逆地理编码：https://lbs.amap.com/api/webservice/guide/api/georegeo
- 高德路径规划 2.0：https://lbs.amap.com/api/webservice/guide/api/newroute
- 高德 JS API 2.0 快速上手：https://lbs.amap.com/api/javascript-api-v2/getting-started
- 高德 JS API 安全密钥：https://lbs.amap.com/api/jsapi-v2/guide/abc/prepare

### 3.2 后端调用原则

| 原则 | 要求 |
|---|---|
| Web Service Key 不进浏览器 | 只在 `AmapService` 后端使用 |
| 坐标精度 | 经度、纬度保留 6 位以内 |
| 坐标系 | 高德返回和展示统一用 GCJ-02 |
| 上海限定 | geocode 请求必须传 `city=上海`；返回结果必须校验 city/province/district |
| 费用与配额控制 | 先用数据库粗筛 Top N，再调用高德；通勤结果缓存 |
| 降级 | 高德失败时返回 `route_status=unavailable`，不让 LLM 编造通勤时长 |
| 审计 | 保存原始请求摘要、响应摘要、耗时、错误码 |

---

## 4. 新增目录结构

在上一版仓库中新增或修改以下文件：

```text
shanghai-re-agent/
  app/
    models/
      geo.py
      rental_listing.py
      commute.py
      social_insight.py
    schemas/
      geo.py
      rental.py
      commute.py
      map.py
      social_insight.py
    services/
      amap_service.py
      geocoding_service.py
      commute_service.py
      commute_cache_service.py
      rental_data_service.py
      rental_scoring_service.py
      map_layer_service.py
      social_insight_service.py
    agents/
      commute_agent.py
      rental_recommendation_agent.py
      map_visualization_agent.py
      social_insight_agent.py
      data_availability_agent.py
    api/
      routes/
        geo.py
        commute.py
        rental.py
        map.py
        insights.py
    templates/
      map.html
    static/
      map.js
      map.css
  scripts/
    seed_shanghai_geo_data.py
    seed_demo_rental_listings.py
    import_rental_listings_csv.py
  data/
    demo/
      rental_listings_demo.csv
      shanghai_candidate_areas.csv
      shanghai_metro_stations_sample.csv
  tests/
    test_commute_scoring.py
    test_map_geojson.py
    test_rental_recommendation.py
    test_amap_service_without_key.py
    test_data_availability_agent.py
```

---

## 5. 新增数据库模型

### 5.1 `RentalListing`

文件：`app/models/rental_listing.py`

```python
class RentalListing(Base):
    __tablename__ = "rental_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None]
    source: Mapped[str] = mapped_column(default="demo")
    title: Mapped[str]

    city: Mapped[str] = mapped_column(index=True, default="上海")
    district: Mapped[str | None] = mapped_column(index=True)
    subdistrict: Mapped[str | None]
    community_name: Mapped[str | None]
    address: Mapped[str | None]

    lng: Mapped[float | None]
    lat: Mapped[float | None]
    coordinate_system: Mapped[str] = mapped_column(default="gcj02")

    rent_monthly: Mapped[int] = mapped_column(index=True)
    deposit_months: Mapped[float | None]
    payment_cycle: Mapped[str | None]

    rooms: Mapped[int | None]
    halls: Mapped[int | None]
    bathrooms: Mapped[int | None]
    area_sqm: Mapped[float | None]
    floor: Mapped[int | None]
    total_floors: Mapped[int | None]
    orientation: Mapped[str | None]
    decoration: Mapped[str | None]
    has_elevator: Mapped[bool | None]

    nearby_metro_station: Mapped[str | None]
    metro_distance_m: Mapped[int | None]

    available_from: Mapped[date | None]
    status: Mapped[str] = mapped_column(default="available", index=True)
    last_seen_at: Mapped[datetime | None]
    listing_url: Mapped[str | None]

    is_verified: Mapped[bool] = mapped_column(default=False)
    is_demo: Mapped[bool] = mapped_column(default=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

约束：

```text
city 必须为上海，否则拒绝入库。
真实推荐只允许 status='available' 且 is_demo=false 的房源。
demo 模式允许展示 is_demo=true，但 UI 必须明确标注。
```

### 5.2 `UserAnchor`

用户锚点，例如公司、学校、伴侣公司、常去地点。

文件：`app/models/geo.py`

```python
class UserAnchor(Base):
    __tablename__ = "user_anchors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    label: Mapped[str]
    anchor_type: Mapped[str]  # workplace / school / family / frequent_place / other
    address: Mapped[str]
    city: Mapped[str] = mapped_column(default="上海")
    district: Mapped[str | None]
    lng: Mapped[float | None]
    lat: Mapped[float | None]
    coordinate_system: Mapped[str] = mapped_column(default="gcj02")
    weight: Mapped[float] = mapped_column(default=1.0)
    arrival_time: Mapped[str | None]  # HH:MM，例如 09:30
    allowed_modes: Mapped[list[str] | None] = mapped_column(JSONB)  # transit/bicycling/driving/walking
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

### 5.3 `CommuteCache`

文件：`app/models/commute.py`

```python
class CommuteCache(Base):
    __tablename__ = "commute_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(default="amap")
    mode: Mapped[str] = mapped_column(index=True)  # transit/driving/walking/bicycling/electrobike

    origin_lng: Mapped[float]
    origin_lat: Mapped[float]
    destination_lng: Mapped[float]
    destination_lat: Mapped[float]
    city1: Mapped[str | None]
    city2: Mapped[str | None]

    cache_key: Mapped[str] = mapped_column(unique=True, index=True)
    route_status: Mapped[str]  # ok/error/unavailable
    duration_min: Mapped[float | None]
    distance_m: Mapped[int | None]
    transfers: Mapped[int | None]
    walking_distance_m: Mapped[int | None]
    taxi_cost_yuan: Mapped[float | None]
    summary: Mapped[str | None]

    route_polyline: Mapped[dict | None] = mapped_column(JSONB)  # GeoJSON LineString
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(index=True)
```

### 5.4 `CandidateArea`

用于没有真实房源数据时推荐区域、板块、地铁站周边。

```python
class CandidateArea(Base):
    __tablename__ = "candidate_areas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    area_type: Mapped[str]  # district/subdistrict/metro_station/community/business_area
    city: Mapped[str] = mapped_column(default="上海", index=True)
    district: Mapped[str | None] = mapped_column(index=True)
    lng: Mapped[float]
    lat: Mapped[float]
    coordinate_system: Mapped[str] = mapped_column(default="gcj02")
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    typical_rent_1br: Mapped[int | None]
    typical_rent_2br: Mapped[int | None]
    metro_lines: Mapped[list[str] | None] = mapped_column(JSONB)
    description: Mapped[str | None]
    is_demo: Mapped[bool] = mapped_column(default=True)
```

### 5.5 `SocialInsight`

用于把小红书/用户截图观点转为可调权重，不抓取平台，只处理用户主动上传或粘贴的内容。

```python
class SocialInsight(Base):
    __tablename__ = "social_insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str]  # pasted_text / uploaded_image
    source_note: Mapped[str | None]
    extracted_text: Mapped[str | None]
    extracted_criteria: Mapped[dict] = mapped_column(JSONB)
    suggested_weights: Mapped[dict] = mapped_column(JSONB)
    caution_notes: Mapped[list[str] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

---

## 6. Pydantic Schema 设计

### 6.1 租房推荐请求

文件：`app/schemas/rental.py`

```python
class AnchorInput(BaseModel):
    label: str
    address: str | None = None
    lng: float | None = None
    lat: float | None = None
    anchor_type: Literal["workplace", "school", "family", "frequent_place", "other"] = "workplace"
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    arrival_time: str | None = None

class RentalPreferenceWeights(BaseModel):
    commute: float = 0.35
    budget: float = 0.25
    transit_access: float = 0.15
    listing_quality: float = 0.10
    amenities: float = 0.10
    risk: float = 0.05

class RentalRecommendationRequest(BaseModel):
    query: str | None = None
    customer_id: str | None = None
    budget_monthly: int | None = Field(default=None, ge=0)
    min_rent_monthly: int | None = None
    max_rent_monthly: int | None = None
    rooms: int | None = None
    preferred_districts: list[str] = Field(default_factory=list)
    excluded_districts: list[str] = Field(default_factory=list)
    anchors: list[AnchorInput] = Field(default_factory=list)
    max_commute_min: int = Field(default=45, ge=5, le=180)
    commute_modes: list[Literal["transit", "bicycling", "driving", "walking", "electrobike"]] = Field(default_factory=lambda: ["transit"])
    weights: RentalPreferenceWeights = Field(default_factory=RentalPreferenceWeights)
    require_metro_distance_m: int | None = None
    allow_demo_data: bool = True
    result_limit: int = Field(default=10, ge=1, le=50)
```

### 6.2 推荐结果

```python
class CommuteRouteSummary(BaseModel):
    anchor_label: str
    mode: str
    duration_min: float | None
    distance_m: int | None
    transfers: int | None = None
    walking_distance_m: int | None = None
    summary: str | None = None
    route_status: Literal["ok", "error", "unavailable"]
    route_geojson: dict | None = None

class RentalRecommendationItem(BaseModel):
    item_type: Literal["listing", "area"]
    id: str
    title: str
    city: str = "上海"
    district: str | None
    community_name: str | None = None
    address: str | None = None
    lng: float
    lat: float
    rent_monthly: int | None = None
    is_demo: bool
    data_source: str
    total_score: float
    score_breakdown: dict[str, float]
    commute_routes: list[CommuteRouteSummary]
    recommendation_reason: str
    risk_notes: list[str]
    next_action: str

class RentalRecommendationResponse(BaseModel):
    mode: Literal["area_mode", "listing_mode", "demo_listing_mode"]
    data_warning: str | None
    request_summary: dict
    results: list[RentalRecommendationItem]
    map_layers: dict
    audit_id: str | None = None
```

### 6.3 地图层响应

文件：`app/schemas/map.py`

```python
class MapLayerResponse(BaseModel):
    center: dict[str, float]
    zoom: int = 12
    markers_geojson: dict
    routes_geojson: dict
    areas_geojson: dict | None = None
    legend: dict
```

---

## 7. 服务层实现

### 7.1 `AmapService`

文件：`app/services/amap_service.py`

职责：封装所有高德后端 HTTP 调用。禁止在 Agent 里直接拼接高德 URL。

必须实现的方法：

```python
class AmapService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient): ...

    async def geocode(self, address: str, city: str = "上海") -> GeocodeResult: ...

    async def reverse_geocode(self, lng: float, lat: float) -> ReverseGeocodeResult: ...

    async def route(
        self,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
        mode: Literal["transit", "driving", "walking", "bicycling", "electrobike"] = "transit",
        city1: str = "021",
        city2: str = "021",
    ) -> RouteResult: ...
```

接口映射：

| mode | endpoint |
|---|---|
| `driving` | `https://restapi.amap.com/v5/direction/driving` |
| `walking` | `https://restapi.amap.com/v5/direction/walking` |
| `bicycling` | `https://restapi.amap.com/v5/direction/bicycling` |
| `electrobike` | `https://restapi.amap.com/v5/direction/electrobike` |
| `transit` | `https://restapi.amap.com/v5/direction/transit/integrated` |

实现要求：

```text
1. 每个请求必须设置 output=json。
2. transit 必须传 city1/city2，默认上海 021；如果 geocode 返回 citycode，则优先使用返回 citycode。
3. driving/walking/bicycling/electrobike 使用 origin 和 destination。
4. show_fields 尽量请求 cost/polyline/navi，但如果接口报错，降级到基础字段。
5. 解析 duration 秒 -> 分钟，distance 米，transfers，walking_distance。
6. 提取 polyline 为 GeoJSON LineString。
7. 所有异常返回 RouteResult(route_status='error')，不得抛到 Agent 层导致整体失败。
```

### 7.2 `CommuteCacheService`

文件：`app/services/commute_cache_service.py`

职责：避免每次推荐都重复调用高德。

cache key 规则：

```python
def build_commute_cache_key(origin_lng, origin_lat, dest_lng, dest_lat, mode):
    return sha256(f"{round(origin_lng, 5)},{round(origin_lat, 5)}->{round(dest_lng, 5)},{round(dest_lat, 5)}:{mode}".encode()).hexdigest()
```

缓存策略：

| 数据 | TTL |
|---|---:|
| geocode | 30 天 |
| reverse geocode | 30 天 |
| commute route | 7 天 |
| demo 数据评分 | 可长期缓存，但 query 变化后重算 |

### 7.3 `CommuteService`

文件：`app/services/commute_service.py`

职责：给候选房源/区域批量计算通勤。

流程：

```text
1. 确保用户 anchor 有坐标；没有则调用 geocode。
2. 对候选 listing/area 粗筛，最多取 50 个点。
3. 对每个候选点、每个 anchor、每个 mode 生成路线任务。
4. 先查 CommuteCache。
5. 未命中则调用 AmapService.route。
6. 使用 asyncio.Semaphore 控制并发，默认 4。
7. 返回每个候选点的最优 mode 和详细 route summaries。
```

### 7.4 `RentalScoringService`

文件：`app/services/rental_scoring_service.py`

职责：确定性打分。LLM 只能解释结果，不能替代打分函数。

#### 7.4.1 预算评分

```python
def budget_score(rent: int | None, budget: int | None, min_rent: int | None = None, max_rent: int | None = None) -> float:
    if rent is None or budget is None:
        return 50.0
    if rent <= budget * 0.85:
        return 100.0
    if rent <= budget:
        return 90.0 - (rent - budget * 0.85) / (budget * 0.15) * 15.0
    if rent <= budget * 1.15:
        return 70.0 - (rent - budget) / (budget * 0.15) * 35.0
    return 20.0
```

#### 7.4.2 通勤评分

```python
def commute_duration_score(duration_min: float | None, target_min: int) -> float:
    if duration_min is None:
        return 30.0
    if duration_min <= target_min * 0.8:
        return 100.0
    if duration_min <= target_min:
        # target*0.8 到 target，从 100 降到 80
        return 100.0 - (duration_min - target_min * 0.8) / (target_min * 0.2) * 20.0
    if duration_min <= target_min + 15:
        # 超出 15 分钟内，从 80 降到 55
        return 80.0 - (duration_min - target_min) / 15.0 * 25.0
    if duration_min <= target_min + 30:
        # 超出 30 分钟内，从 55 降到 25
        return 55.0 - (duration_min - target_min - 15) / 15.0 * 30.0
    return 10.0
```

换乘和步行惩罚：

```python
def commute_penalty(transfers: int | None, walking_distance_m: int | None) -> float:
    transfer_penalty = max(0, (transfers or 0) - 1) * 8.0
    walk_penalty = 0.0
    if walking_distance_m and walking_distance_m > 800:
        walk_penalty = min(15.0, (walking_distance_m - 800) / 100 * 1.5)
    return transfer_penalty + walk_penalty
```

多锚点评分：

```python
def multi_anchor_commute_score(anchor_scores: list[tuple[float, float]]) -> float:
    # list[(score, weight)]
    total_weight = sum(w for _, w in anchor_scores) or 1.0
    weighted = sum(score * weight for score, weight in anchor_scores) / total_weight
    worst = min(score for score, _ in anchor_scores) if anchor_scores else weighted
    # 上海租房场景里，最差通勤点也很重要，所以加入 20% worst-case
    return 0.8 * weighted + 0.2 * worst
```

#### 7.4.3 地铁便利评分

```python
def transit_access_score(metro_distance_m: int | None) -> float:
    if metro_distance_m is None:
        return 50.0
    if metro_distance_m <= 500:
        return 100.0
    if metro_distance_m <= 800:
        return 90.0
    if metro_distance_m <= 1200:
        return 70.0
    if metro_distance_m <= 1800:
        return 45.0
    return 20.0
```

#### 7.4.4 风险评分

风险分不是“风险越高分越高”，而是“安全程度分”。

```python
def risk_score(item) -> tuple[float, list[str]]:
    score = 100.0
    notes = []
    if getattr(item, "is_demo", False):
        score -= 20
        notes.append("该条为 demo 数据，不能作为真实可租房源")
    if getattr(item, "is_verified", False) is False:
        score -= 15
        notes.append("房源未标记为已核验")
    if getattr(item, "status", "unknown") != "available":
        score -= 40
        notes.append("房源状态不是 available")
    if getattr(item, "last_seen_at", None) is None:
        score -= 10
        notes.append("缺少最近更新时间")
    return max(score, 0.0), notes
```

#### 7.4.5 综合评分

默认权重：

```python
DEFAULT_RENTAL_WEIGHTS = {
    "commute": 0.35,
    "budget": 0.25,
    "transit_access": 0.15,
    "listing_quality": 0.10,
    "amenities": 0.10,
    "risk": 0.05,
}
```

综合公式：

```python
total_score = (
    weights.commute * commute_score
    + weights.budget * budget_score
    + weights.transit_access * transit_access_score
    + weights.listing_quality * listing_quality_score
    + weights.amenities * amenities_score
    + weights.risk * risk_score_value
)
```

---

## 8. 新增 Agent 设计

### 8.1 `SocialInsightAgent`

用途：把小红书用户观点、用户截图、租房笔记转成结构化租房决策因素。

输入：

```json
{
  "source_type": "uploaded_image",
  "image_path": "uploads/xhs_note.png",
  "user_context": "准备用于上海租房推荐 Agent 的偏好权重"
}
```

输出：

```json
{
  "extracted_text": "...",
  "criteria": [
    {"name": "通勤时间", "importance": "high", "scoring_hint": "优先控制在45分钟以内"},
    {"name": "地铁便利", "importance": "medium", "scoring_hint": "距离地铁800米以内更优"},
    {"name": "预算压力", "importance": "high", "scoring_hint": "不要只看最低价，要看押付和水电网"}
  ],
  "suggested_weights": {
    "commute": 0.40,
    "budget": 0.25,
    "transit_access": 0.15,
    "listing_quality": 0.10,
    "amenities": 0.05,
    "risk": 0.05
  },
  "caution_notes": ["社交平台观点只能作为偏好参考，不能替代真实房源核验"]
}
```

实现方式：

- 图片输入：调用 OpenAI Vision 能力读取截图；
- 文本输入：调用 OpenAI Structured Outputs；
- 存库：`SocialInsight`；
- 不直接改系统默认权重，除非用户显式选择“应用该观点权重”。

System prompt：

```text
你是上海租房偏好分析 Agent。你的任务是把用户上传或粘贴的租房观点转成可执行的选房评分因素。
要求：
1. 不要把社交平台观点当作事实，只能作为偏好或经验。
2. 输出必须是结构化 JSON。
3. 评分因素必须能映射到系统已有维度：commute、budget、transit_access、listing_quality、amenities、risk。
4. 如果观点包含夸张、绝对化、不可验证内容，放入 caution_notes。
5. 不要推荐具体房源。
```

### 8.2 `CommuteAgent`

用途：根据用户工作地点/常去地点，计算每个候选房源或区域的通勤。

输入：

```json
{
  "candidate": {"id": "...", "lng": 121.48, "lat": 31.22, "type": "listing"},
  "anchors": [
    {"label": "公司", "address": "上海市浦东新区张江高科", "weight": 1.0}
  ],
  "modes": ["transit", "bicycling"],
  "max_commute_min": 45
}
```

实现链路：

```text
CommuteAgent
  -> GeocodingService.ensure_anchor_coordinates()
  -> CommuteService.batch_estimate()
  -> CommuteCacheService.get_or_create()
  -> AmapService.route()
  -> RentalScoringService.commute_score()
```

LLM 使用点：

- 不用于计算时间；
- 只用于把路线结果解释成人话，例如“地铁为主，步行距离略长”。

System prompt：

```text
你是上海租房通勤分析 Agent。你只能基于工具返回的高德路线结果解释通勤，不允许编造时间、距离、路线、换乘次数。
如果路线不可用，必须说明“暂未取得路线结果”。
输出包括：通勤时长、主要出行方式、换乘/步行负担、是否超过用户阈值、对选房的影响。
```

### 8.3 `RentalRecommendationAgent`

用途：把房源/区域筛选、通勤计算、评分、推荐解释串起来。

核心流程：

```text
1. CityGuard：确认所有地址和候选项属于上海。
2. CustomerNeedAgent：从 query 中抽取预算、房型、通勤点、通勤阈值、偏好。
3. DataAvailabilityAgent：判断走 listing_mode / area_mode / demo_listing_mode。
4. RentalDataService：取候选房源或候选区域。
5. CommuteAgent：计算候选点到 anchors 的通勤。
6. RentalScoringService：确定性综合打分。
7. OpenAI RecommendationExplainer：生成推荐理由和 trade-off。
8. ComplianceAgent：检查是否声称真实房源、是否超出上海、是否虚假承诺。
9. MapLayerService：生成地图层。
```

System prompt：

```text
你是上海租房推荐 Agent。你只服务上海。
你必须遵守：
1. 不能推荐上海以外地点。
2. 没有真实房源数据时，只能推荐区域、板块、地铁站周边或 demo 房源，必须明确标注数据限制。
3. 通勤时间、路线、距离只能来自工具结果，不能自行估计。
4. 具体房源必须带数据来源、更新时间、状态和是否 demo。
5. 推荐理由必须解释取舍：预算、通勤、地铁便利、房源质量、风险。
6. 不做“保证租到”“保证真实”“保证涨价/降价”等承诺。
```

### 8.4 `MapVisualizationAgent`

用途：把推荐结果转换成前端可画的 GeoJSON 和 UI 卡片。

实现上可以不用 LLM，纯代码更稳定。

输出图层：

```json
{
  "center": {"lng": 121.4737, "lat": 31.2304},
  "zoom": 12,
  "markers_geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "routes_geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "areas_geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "legend": {
    "score": "score >= 85 优先；70-85 可考虑；<70 谨慎"
  }
}
```

Marker properties：

```json
{
  "id": "...",
  "title": "徐汇漕河泾附近 demo 房源",
  "item_type": "listing",
  "score": 86.4,
  "rent_monthly": 5200,
  "district": "徐汇区",
  "commute_min": 38,
  "is_demo": true,
  "risk_notes": ["demo 数据，不能作为真实可租房源"]
}
```

### 8.5 `DataAvailabilityAgent`

用途：防止系统在无真实房源时“装作有真实房源”。

逻辑：

```python
def decide_mode(available_real_count: int, available_demo_count: int, allow_demo: bool) -> DataMode:
    if available_real_count > 0:
        return "listing_mode"
    if allow_demo and available_demo_count > 0:
        return "demo_listing_mode"
    return "area_mode"
```

输出 warning：

```text
当前系统尚未接入真实租房平台或公司库存数据。以下结果为区域/样例房源推荐，用于说明算法和通勤可视化，不代表真实可租房源。
```

---

## 9. API 设计

### 9.1 地理编码

```http
POST /api/geo/geocode
```

Request：

```json
{
  "address": "张江高科",
  "city": "上海"
}
```

Response：

```json
{
  "address": "张江高科",
  "city": "上海",
  "district": "浦东新区",
  "lng": 121.598,
  "lat": 31.207,
  "coordinate_system": "gcj02",
  "provider": "amap"
}
```

### 9.2 单点通勤估算

```http
POST /api/commute/estimate
```

Request：

```json
{
  "origin": {"lng": 121.45, "lat": 31.22, "label": "候选房源"},
  "destination": {"address": "上海市浦东新区张江高科", "label": "公司"},
  "modes": ["transit", "bicycling"],
  "city": "上海"
}
```

### 9.3 租房推荐

```http
POST /api/rental/recommend
```

Request：

```json
{
  "query": "我在张江上班，预算5500，想租一室户，通勤45分钟以内，最好近地铁",
  "budget_monthly": 5500,
  "rooms": 1,
  "anchors": [
    {
      "label": "公司",
      "address": "上海市浦东新区张江高科",
      "anchor_type": "workplace",
      "weight": 1.0,
      "arrival_time": "09:30"
    }
  ],
  "commute_modes": ["transit", "bicycling"],
  "max_commute_min": 45,
  "allow_demo_data": true,
  "result_limit": 10
}
```

### 9.4 地图推荐结果

```http
POST /api/map/rental-recommendations
```

返回：

```json
{
  "mode": "demo_listing_mode",
  "data_warning": "当前为 demo 数据，不代表真实可租房源。",
  "map_layers": {
    "center": {"lng": 121.47, "lat": 31.23},
    "markers_geojson": {},
    "routes_geojson": {},
    "legend": {}
  },
  "results": []
}
```

### 9.5 社交观点/截图提取

```http
POST /api/insights/social
```

支持：

- `multipart/form-data` 上传图片；
- 或 JSON 粘贴文本。

返回结构化评分因素和建议权重。

---

## 10. 地图前端实现：先用最小 HTML，不上复杂前端框架

上一版方案先做 FastAPI + Swagger。现在可以补一个轻量地图页：

```text
GET /map
```

文件：`app/templates/map.html`

页面元素：

```text
左侧控制面板：
  - 工作地点输入框
  - 月租预算
  - 户型
  - 最大通勤时间
  - 出行方式：公交/骑行/驾车/步行
  - 是否允许 demo 数据
  - 推荐按钮

右侧地图：
  - AMap 地图容器
  - 房源/区域 Marker
  - 点击 Marker 展示信息窗体
  - 点击“显示路线”绘制 Polyline

底部列表：
  - 推荐卡片
  - 总分、预算分、通勤分、地铁分、风险提示
```

### 10.1 `map.html` 加载方式

本地开发可以：

```html
<script type="text/javascript">
  window._AMapSecurityConfig = {
    securityJsCode: "{{ amap_js_security_code }}"
  };
</script>
<script src="https://webapi.amap.com/loader.js"></script>
<script>
  window.APP_CONFIG = {
    amapKey: "{{ amap_js_api_key }}"
  };
</script>
<script src="/static/map.js"></script>
```

生产环境不要把安全密钥明文暴露到前端，改为代理方式。

### 10.2 `map.js` 核心逻辑

```javascript
async function initMap() {
  const AMap = await AMapLoader.load({
    key: window.APP_CONFIG.amapKey,
    version: "2.0"
  });

  window.map = new AMap.Map("map", {
    zoom: 12,
    center: [121.4737, 31.2304]
  });
}

async function recommend() {
  const payload = collectForm();
  const res = await fetch("/api/map/rental-recommendations", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  renderMarkers(data.map_layers.markers_geojson);
  renderResultCards(data.results);
  showWarning(data.data_warning);
}

function renderMarkers(geojson) {
  clearMarkers();
  geojson.features.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const p = feature.properties;
    const marker = new AMap.Marker({
      position: [lng, lat],
      title: p.title,
      label: {content: `${Math.round(p.score)}`}
    });
    marker.on("click", () => openInfoWindow(feature));
    window.map.add(marker);
    window.markers.push(marker);
  });
}
```

---

## 11. Demo 数据设计

### 11.1 `rental_listings_demo.csv`

必须标记 `is_demo=true`。示例：

```csv
external_id,source,title,city,district,community_name,address,lng,lat,coordinate_system,rent_monthly,rooms,halls,bathrooms,area_sqm,nearby_metro_station,metro_distance_m,status,is_verified,is_demo,last_seen_at
D001,demo,张江附近一室户样例,上海,浦东新区,张江样例小区,上海市浦东新区张江高科附近,121.598,31.207,gcj02,5600,1,1,1,38,张江高科,650,available,false,true,2026-01-01T00:00:00
D002,demo,漕河泾通勤样例房,上海,徐汇区,漕河泾样例小区,上海市徐汇区漕河泾附近,121.408,31.176,gcj02,5300,1,1,1,35,漕河泾开发区,700,available,false,true,2026-01-01T00:00:00
```

### 11.2 `shanghai_candidate_areas.csv`

用于 `area_mode`：

```csv
name,area_type,city,district,lng,lat,typical_rent_1br,typical_rent_2br,metro_lines,tags,is_demo
张江高科周边,metro_station,上海,浦东新区,121.598,31.207,5800,8500,"[\"2号线\"]","[\"科技园\",\"通勤便利\"]",true
漕河泾开发区周边,metro_station,上海,徐汇区,121.408,31.176,5600,8200,"[\"9号线\"]","[\"产业园\",\"办公\"]",true
中山公园周边,metro_station,上海,长宁区,121.424,31.224,6500,9800,"[\"2号线\",\"3号线\",\"4号线\"]","[\"换乘\",\"生活便利\"]",true
```

---

## 12. 和上一版 Agent 的整合点

### 12.1 `SupervisorAgent` 增加意图

新增 intent：

```python
Literal[
  "rental_map_recommendation",
  "commute_analysis",
  "social_insight_extraction",
  "rental_data_import",
]
```

路由规则：

| 用户话术 | 路由 |
|---|---|
| “地图上列出来” | `rental_map_recommendation` |
| “帮我算通勤” | `commute_analysis` |
| “我在XX上班，预算XX，租哪里” | `rental_map_recommendation` |
| “看这张小红书截图，总结选房标准” | `social_insight_extraction` |
| “导入房源表” | `rental_data_import` |

### 12.2 `CustomerNeedAgent` 增强字段

必须能从自然语言抽取：

```json
{
  "rental": {
    "budget_monthly": 5500,
    "rooms": 1,
    "max_commute_min": 45,
    "commute_modes": ["transit"],
    "anchors": [
      {"label": "公司", "address": "张江", "anchor_type": "workplace", "weight": 1.0}
    ],
    "preferences": {
      "near_metro": true,
      "avoid_old_building": true,
      "quiet": false
    }
  }
}
```

### 12.3 `ListingAgent` 增强为 `RentalRecommendationAgent` 的工具

`ListingAgent` 继续负责结构化房源检索；`RentalRecommendationAgent` 负责把通勤和地图加入排序。

---

## 13. OpenAI API 使用安排

| 场景 | OpenAI 作用 | 是否必须 |
|---|---|---:|
| 自然语言租房需求抽取 | 把“预算、工作地、通勤、房型、偏好”转 JSON | 必须 |
| 小红书截图/观点提取 | Vision + Structured Output 提取偏好权重 | 可选但建议 |
| 推荐解释 | 把确定性分数解释成用户能理解的话 | 必须 |
| 通勤路线解释 | 根据高德结果总结路线优劣 | 可选 |
| 合规检查 | 检查是否把 demo 当真实、是否超出上海、是否虚假承诺 | 必须 |
| 房源文案 | 延续上一版营销 Agent | 可选 |

注意：

```text
OpenAI 不负责：
  - 计算通勤时间；
  - 判断真实房源可租状态；
  - 编造地图坐标；
  - 编造地铁距离；
  - 替代平台/公司房源数据。
```

---

## 14. 本地运行命令变化

新增依赖：

```bash
pip install httpx jinja2 aiofiles
```

重新初始化：

```bash
python scripts/init_db.py
python scripts/seed_demo_data.py
python scripts/seed_shanghai_geo_data.py
python scripts/seed_demo_rental_listings.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：

```text
Swagger: http://localhost:8000/docs
地图页: http://localhost:8000/map
```

---

## 15. 验收用例

### 15.1 无真实房源时必须降级

输入：

```json
{
  "query": "我在张江上班，预算5500，想租一室户，通勤45分钟以内",
  "allow_demo_data": false
}
```

期望：

```text
mode = area_mode
不返回具体 demo 房源
返回候选区域/地铁站周边
data_warning 明确说明未接入真实房源
```

### 15.2 demo 房源必须打标

输入：

```json
{
  "query": "我在张江上班，预算5500，想租一室户",
  "allow_demo_data": true
}
```

期望：

```text
mode = demo_listing_mode
每个 result.is_demo = true
data_warning 不为空
风险提示包含“demo 数据，不能作为真实可租房源”
```

### 15.3 上海以外拒绝

输入：

```json
{
  "query": "我在苏州工业园区上班，帮我推荐昆山租房"
}
```

期望：

```text
拒绝推荐上海以外房源
说明公司只服务上海
不调用高德路线或房源推荐
```

### 15.4 通勤不得编造

在未配置 `AMAP_WEB_SERVICE_KEY` 时：

```text
路线状态必须是 unavailable/error
推荐解释中不得出现具体“37分钟”这类伪造时间
可使用 demo fallback 提示：需要配置高德 Key 后才能计算真实路线
```

### 15.5 地图 GeoJSON 合法

测试：

```bash
pytest tests/test_map_geojson.py
```

要求：

```text
FeatureCollection 格式合法
坐标为 [lng, lat]
所有 marker 在上海范围内
route polyline 为 LineString
```

---

## 16. 实施优先级

### P0：1–2 天

- 新增 `.env.example` 高德配置；
- 新增 demo 租房 CSV；
- 新增 `RentalListing`、`CandidateArea`、`CommuteCache` 模型；
- 新增 CSV import/seed 脚本；
- 新增租房推荐 API 的 demo 版。

### P1：2–4 天

- 实现 `AmapService.geocode()`；
- 实现 `AmapService.route()`；
- 实现 `CommuteService` 和缓存；
- 实现 `RentalScoringService`；
- 把通勤分纳入推荐。

### P2：2–3 天

- 实现 `/map` 地图页；
- Marker、信息窗体、推荐卡片；
- 点击结果显示路线 polyline；
- 添加数据警示和 demo 标识。

### P3：1–2 天

- 实现 `SocialInsightAgent`；
- 支持上传截图或粘贴观点；
- 生成偏好权重；
- 可在推荐请求中应用该权重。

---

## 17. 发给 Codex 的实现 Prompt

下面这段可以直接发给 Codex。假设上一版方案已经生成了 `shanghai-re-agent` 仓库。

```text
你现在在已有的 shanghai-re-agent 仓库中做增量开发。不要重写已有项目，不要删除已有 Agent。请基于现有 FastAPI + SQLAlchemy + PostgreSQL/pgvector + OpenAI API 架构，新增“上海租房地图推荐 + 高德通勤评分”能力。

硬性要求：
1. 公司只服务上海。所有新增房源、区域、地图点、通勤起终点都必须经过上海限定校验。上海以外直接拒绝推荐。
2. 当前没有真实租房平台数据。系统必须支持三种模式：
   - listing_mode：有真实房源时才用；
   - demo_listing_mode：只有 demo 房源时用于演示，必须明确标注 demo；
   - area_mode：没有房源时只推荐区域/地铁站/板块，不推荐具体房子。
3. 不允许编造真实房源、通勤时间、路线、地铁距离。通勤时间必须来自 AmapService 或标记 unavailable。
4. OpenAI API 只能用于自然语言抽取、观点/截图提取、解释、合规检查；不能替代确定性评分和路线计算。
5. 所有 API Key 通过 .env 读取，不得硬编码。

请新增或修改以下内容：

A. 配置
- 在 app/config.py 和 .env.example 中加入：
  AMAP_WEB_SERVICE_KEY
  AMAP_JS_API_KEY
  AMAP_JS_SECURITY_CODE
  AMAP_DEFAULT_CITY=上海
  AMAP_DEFAULT_CITY_CODE=021
  AMAP_CACHE_TTL_HOURS=168
  AMAP_LIVE_CALL_CONCURRENCY=4
  AMAP_ENABLE_LIVE=true
  ENABLE_DEMO_RENTAL_DATA=true

B. 模型
新增：
- app/models/rental_listing.py: RentalListing
- app/models/geo.py: UserAnchor, CandidateArea
- app/models/commute.py: CommuteCache
- app/models/social_insight.py: SocialInsight
字段按本文档定义实现。city 必须默认上海。demo 数据必须有 is_demo 字段。

C. Schema
新增：
- app/schemas/rental.py: RentalRecommendationRequest, RentalRecommendationResponse, RentalRecommendationItem, AnchorInput, RentalPreferenceWeights
- app/schemas/commute.py: CommuteEstimateRequest, CommuteEstimateResponse, CommuteRouteSummary
- app/schemas/geo.py: GeocodeRequest, GeocodeResponse
- app/schemas/map.py: MapLayerResponse
- app/schemas/social_insight.py: SocialInsightRequest, SocialInsightResponse

D. Services
新增：
- app/services/amap_service.py
  实现 geocode(), reverse_geocode(), route()。
  后端调用高德 Web 服务 API。支持 transit/driving/walking/bicycling/electrobike。
  没有 AMAP_WEB_SERVICE_KEY 或 AMAP_ENABLE_LIVE=false 时返回 unavailable，不要抛出未处理异常。

- app/services/commute_cache_service.py
  实现通勤缓存。cache_key 使用坐标四舍五入到 5 位 + mode 的 sha256。

- app/services/commute_service.py
  实现 batch_estimate()。先查缓存，再调用 AmapService。使用 asyncio.Semaphore 控制并发。

- app/services/rental_data_service.py
  实现 get_candidate_listings()、get_candidate_areas()、count_available_real_listings()、count_demo_listings()。
  优先按 city=上海、status=available、预算、户型、区县粗筛。

- app/services/rental_scoring_service.py
  实现 budget_score、commute_duration_score、commute_penalty、multi_anchor_commute_score、transit_access_score、risk_score、total_score。
  评分函数必须可单元测试。

- app/services/map_layer_service.py
  把推荐结果转为 GeoJSON FeatureCollection：markers_geojson、routes_geojson、areas_geojson。

- app/services/social_insight_service.py
  调用现有 OpenAIService，用结构化输出从用户粘贴文本或上传图片中抽取租房偏好和建议权重。

E. Agents
新增：
- app/agents/data_availability_agent.py
  根据真实房源数量、demo 房源数量、allow_demo_data 决定 listing_mode/demo_listing_mode/area_mode。

- app/agents/commute_agent.py
  调用 CommuteService，返回每个候选项的通勤摘要和通勤分。不得编造通勤时间。

- app/agents/rental_recommendation_agent.py
  主流程：CityGuard -> CustomerNeedAgent -> DataAvailabilityAgent -> RentalDataService -> CommuteAgent -> RentalScoringService -> OpenAI 解释 -> ComplianceAgent -> MapLayerService。

- app/agents/map_visualization_agent.py
  可简单包装 MapLayerService，生成地图图层。

- app/agents/social_insight_agent.py
  处理小红书/社交平台观点截图或文本，输出 criteria 和 suggested_weights。

同时修改 app/agents/supervisor.py：新增 intents：rental_map_recommendation、commute_analysis、social_insight_extraction、rental_data_import。含“地图”“租哪里”“通勤”“高德”“小红书截图”等话术时路由到新增 Agent。

F. API Routes
新增：
- POST /api/geo/geocode
- POST /api/commute/estimate
- POST /api/rental/recommend
- POST /api/map/rental-recommendations
- POST /api/insights/social
- GET /map

G. 地图前端
新增：
- app/templates/map.html
- app/static/map.js
- app/static/map.css

/map 页面用高德 JS API 2.0 展示地图。页面包含：工作地点、预算、户型、最大通勤、出行方式、是否允许 demo 数据、推荐按钮。调用 /api/map/rental-recommendations，绘制 marker 和路线 polyline。点击 marker 展示总分、租金、通勤、风险提示、是否 demo。

H. Demo 数据与脚本
新增：
- data/demo/rental_listings_demo.csv
- data/demo/shanghai_candidate_areas.csv
- scripts/seed_shanghai_geo_data.py
- scripts/seed_demo_rental_listings.py
- scripts/import_rental_listings_csv.py

CSV 字段按本文档定义。所有 demo 数据必须 is_demo=true。seed 脚本可重复执行，不要重复插入同 external_id。

I. 测试
新增 pytest：
- tests/test_commute_scoring.py：预算分、通勤分、地铁分、综合分。
- tests/test_map_geojson.py：GeoJSON 格式和坐标合法。
- tests/test_rental_recommendation.py：demo_listing_mode、area_mode、上海以外拒绝。
- tests/test_amap_service_without_key.py：无 AMAP key 时返回 unavailable，不抛异常。
- tests/test_data_availability_agent.py：三种模式判断正确。

J. 运行说明
更新 README.md，加入：
- 如何配置 AMAP_WEB_SERVICE_KEY、AMAP_JS_API_KEY、AMAP_JS_SECURITY_CODE；
- 没有高德 key 时怎么跑 demo；
- 没有真实房源数据时系统只做区域/demo 推荐；
- 如何访问 http://localhost:8000/map；
- 如何导入真实房源 CSV。

完成标准：
1. `pytest` 通过。
2. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` 可启动。
3. `GET /map` 可打开地图页。
4. 在未配置高德 key 时，推荐 API 不崩溃，并提示路线不可用。
5. 配置高德 key 后，可以对上海内候选点计算通勤路线。
6. 返回结果中必须有 mode、data_warning、score_breakdown、map_layers。
```

---

## 18. 最终产品形态

这次增量完成后，产品会从“会聊天的房产 Agent”升级为：

```text
上海租房空间决策 Agent
= 用户需求理解
+ 上海限定
+ 房源/区域数据接入
+ 高德地理编码
+ 高德通勤路线
+ 通勤纳入评分
+ 地图可视化
+ 数据真实性警示
+ OpenAI 推荐解释与偏好权重提取
```

当前阶段不要追求“直接给真实房子”。先做：

```text
上海哪些区域/地铁站周边适合我租？
这些选择到公司通勤多久？
预算压力如何？
为什么推荐？
地图上在哪里？
如果以后接入真实房源，哪套房最优？
```

这条路线可落地，也能自然过渡到真实公司库存或授权平台数据。
