let map;
let AMapApi;
let markers = [];
let markersById = new Map();
let polylines = [];
let workMarker;
let geocoder;
let placeSearch;
let selectedWorkAnchor = null;
let latestResults = [];
let selectedRouteItemId = null;
let suppressWorkplaceInput = false;
const agentRouteStorageKey = "rentAgent.agentRouteSelection";
const layoutStorageKeys = {
  sidebarWidth: "rentAgent.map.sidebarWidth",
  resultsHeight: "rentAgent.map.resultsHeight",
  sidebarCollapsed: "rentAgent.map.sidebarCollapsed",
  resultsCollapsed: "rentAgent.map.resultsCollapsed"
};

async function initMap() {
  const key = window.APP_CONFIG && window.APP_CONFIG.amapKey;
  if (!key || !window.AMapLoader) {
    document.getElementById("map").textContent = "未配置 AMAP_JS_API_KEY，地图底图不可用；仍可使用推荐列表。";
    setWorkplaceStatus("未配置高德 JS Key 时不可使用地点联想和地图选点；推荐时会用输入文字尝试定位。", true);
    return;
  }
  const AMap = await AMapLoader.load({
    key,
    version: "2.0",
    plugins: ["AMap.AutoComplete", "AMap.PlaceSearch", "AMap.Geocoder"]
  });
  AMapApi = AMap;
  map = new AMap.Map("map", { zoom: 12, center: [121.4737, 31.2304] });
  initWorkplacePicker(AMap);
  scheduleMapResize();
}

function collectForm() {
  const workplace = document.getElementById("workplace").value.trim();
  const anchor = {
    label: "公司",
    address: normalizeShanghaiAddress(
      selectedWorkAnchor ? selectedWorkAnchor.address : workplace
    ),
    anchor_type: "workplace",
    weight: 1
  };
  if (selectedWorkAnchor && selectedWorkAnchor.lng !== null && selectedWorkAnchor.lat !== null) {
    anchor.lng = selectedWorkAnchor.lng;
    anchor.lat = selectedWorkAnchor.lat;
  }
  return {
    query: `我在${workplace}上班，预算${document.getElementById("budget").value}，想租${document.getElementById("rooms").value}室，通勤${document.getElementById("commute").value}分钟以内`,
    budget_monthly: Number(document.getElementById("budget").value),
    rooms: Number(document.getElementById("rooms").value),
    anchors: [anchor],
    max_commute_min: Number(document.getElementById("commute").value),
    commute_modes: [document.getElementById("mode").value],
    allow_demo_data: false,
    recommendation_unit: "community",
    result_limit: 10
  };
}

async function recommend() {
  const button = document.getElementById("recommend");
  clearStatusMessage();
  setResultsCollapsed(false);
  renderLoadingState();
  button.disabled = true;
  try {
    const res = await fetch("/api/map/rental-recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectForm())
    });
    const data = await res.json();
    if (!res.ok) {
      showStatusMessage(data.detail || "推荐请求失败。");
      renderPendingState("请求未完成", "当前没有可展示的推荐结果。");
      return;
    }
    latestResults = data.results || [];
    selectedRouteItemId = null;
    renderMarkers(data.map_layers && data.map_layers.markers_geojson);
    clearRoutes();
    renderResultCards(latestResults);
  } catch (error) {
    showStatusMessage("网络或服务异常，暂时无法生成推荐。");
    renderPendingState("服务暂不可用", "稍后可继续查看候选结果。");
  } finally {
    button.disabled = false;
  }
}

function clearMap() {
  if (map) {
    markers.forEach(marker => map.remove(marker));
    polylines.forEach(line => map.remove(line));
  }
  markers = [];
  markersById = new Map();
  polylines = [];
}

function clearRoutes() {
  if (map) {
    polylines.forEach(line => map.remove(line));
  }
  polylines = [];
}

function initWorkplaceInput() {
  const input = document.getElementById("workplace");
  input.addEventListener("input", () => {
    if (suppressWorkplaceInput) return;
    selectedWorkAnchor = null;
    removeWorkMarker();
    setWorkplaceStatus("请选择高德联想结果，或在地图上点击一个上海范围内的工作地点。");
  });
}

function initWorkplacePicker(AMap) {
  geocoder = new AMap.Geocoder({ city: "上海", citylimit: true });
  placeSearch = new AMap.PlaceSearch({ city: "上海", citylimit: true });

  const autoComplete = new AMap.AutoComplete({
    city: "上海",
    citylimit: true,
    input: "workplace"
  });

  autoComplete.on("select", event => {
    const poi = event && event.poi ? event.poi : {};
    const location = parseLngLat(poi.location);
    if (location) {
      selectWorkplace({
        name: poi.name || document.getElementById("workplace").value,
        address: formatPoiAddress(poi),
        lng: location.lng,
        lat: location.lat,
        source: "amap_autocomplete"
      });
      return;
    }
    resolvePoiWithoutLocation(poi);
  });

  map.on("click", event => {
    const location = parseLngLat(event.lnglat);
    if (!location) return;
    if (!isProbablyShanghai(location.lng, location.lat)) {
      setWorkplaceStatus("只能选择上海范围内的工作地点。", true);
      return;
    }
    selectWorkplaceFromMap(location.lng, location.lat);
  });

  setWorkplaceStatus("输入工作地点 / 高德地图上点击工作地点");
}

function resolvePoiWithoutLocation(poi) {
  const fallbackName = poi && poi.name ? poi.name : document.getElementById("workplace").value;
  if (poi && poi.id && placeSearch && typeof placeSearch.getDetails === "function") {
    placeSearch.getDetails(poi.id, (status, result) => {
      const detailPoi = firstPoiFromPlaceSearch(result);
      const location = detailPoi ? parseLngLat(detailPoi.location) : null;
      if (status === "complete" && detailPoi && location) {
        selectWorkplace({
          name: detailPoi.name || fallbackName,
          address: formatPoiAddress(detailPoi),
          lng: location.lng,
          lat: location.lat,
          source: "amap_place_detail"
        });
        return;
      }
      geocodeWorkplaceText(fallbackName);
    });
    return;
  }
  geocodeWorkplaceText(fallbackName);
}

function geocodeWorkplaceText(text) {
  if (!geocoder || typeof geocoder.getLocation !== "function") {
    setWorkplaceStatus("已保留输入文字；推荐时会由后端尝试定位。", true);
    return;
  }
  geocoder.getLocation(normalizeShanghaiAddress(text), (status, result) => {
    const location = firstLocationFromGeocode(result);
    if (status === "complete" && location) {
      selectWorkplace({
        name: text,
        address: normalizeShanghaiAddress(text),
        lng: location.lng,
        lat: location.lat,
        source: "amap_geocode"
      });
      return;
    }
    selectedWorkAnchor = null;
    removeWorkMarker();
    setWorkplaceStatus("没有拿到这个地点的经纬度；请从联想列表选择，或直接点击地图。", true);
  });
}

function selectWorkplaceFromMap(lng, lat) {
  setWorkplaceStatus("正在识别地图选点...");
  if (!geocoder || typeof geocoder.getAddress !== "function") {
    selectWorkplace({
      name: "地图选点",
      address: `上海地图选点 ${lng.toFixed(5)}, ${lat.toFixed(5)}`,
      lng,
      lat,
      source: "map_click"
    });
    return;
  }
  geocoder.getAddress([lng, lat], (status, result) => {
    const regeocode = result && result.regeocode ? result.regeocode : null;
    const address = regeocode && regeocode.formattedAddress
      ? regeocode.formattedAddress
      : `上海地图选点 ${lng.toFixed(5)}, ${lat.toFixed(5)}`;
    const poi = firstPoiFromReverseGeocode(regeocode);
    selectWorkplace({
      name: poi && poi.name ? poi.name : shortAddress(address),
      address,
      lng,
      lat,
      source: "map_click"
    });
  });
}

function selectWorkplace(anchor) {
  if (!isProbablyShanghai(anchor.lng, anchor.lat)) {
    selectedWorkAnchor = null;
    removeWorkMarker();
    setWorkplaceStatus("该地点不在上海范围内，不能作为通勤起终点。", true);
    return;
  }
  const input = document.getElementById("workplace");
  selectedWorkAnchor = {
    name: anchor.name || anchor.address || "工作地点",
    address: normalizeShanghaiAddress(anchor.address || anchor.name || input.value),
    lng: Number(anchor.lng),
    lat: Number(anchor.lat),
    source: anchor.source || "amap"
  };
  suppressWorkplaceInput = true;
  input.value = selectedWorkAnchor.name;
  window.setTimeout(() => { suppressWorkplaceInput = false; }, 0);
  updateWorkMarker(selectedWorkAnchor);
  setWorkplaceStatus(
    `已选中：${selectedWorkAnchor.address}（${selectedWorkAnchor.lng.toFixed(5)}, ${selectedWorkAnchor.lat.toFixed(5)}）`
  );
}

function updateWorkMarker(anchor) {
  const AMap = AMapApi || window.AMap;
  if (!map || !AMap) return;
  const position = [anchor.lng, anchor.lat];
  if (!workMarker) {
    workMarker = new AMap.Marker({
      position,
      title: "工作地点",
      content: '<div class="work-marker">工</div>',
      offset: new AMap.Pixel(-15, -15),
      zIndex: 120
    });
    workMarker.on("click", () => {
      const html = `<strong>工作地点</strong><br/>${escapeHtml(selectedWorkAnchor ? selectedWorkAnchor.address : anchor.address)}`;
      new AMap.InfoWindow({ content: html }).open(map, workMarker.getPosition());
    });
    map.add(workMarker);
  } else {
    workMarker.setPosition(position);
  }
  map.setCenter(position);
}

function removeWorkMarker() {
  if (map && workMarker) {
    map.remove(workMarker);
  }
  workMarker = null;
}

function setWorkplaceStatus(text, isWarning = false) {
  const status = document.getElementById("workplaceStatus");
  status.textContent = text;
  status.classList.toggle("field-hint-warning", isWarning);
}

function initResizableLayout() {
  const shell = document.getElementById("layout");
  const mapWrap = document.querySelector(".map-wrap");
  const sidebarResizer = document.getElementById("sidebarResizer");
  const resultsResizer = document.getElementById("resultsResizer");
  const closeSidebar = document.getElementById("closeSidebar");
  const openSidebar = document.getElementById("openSidebar");
  const closeResults = document.getElementById("closeResults");
  const openResults = document.getElementById("openResults");

  const savedSidebarWidth = Number(localStorage.getItem(layoutStorageKeys.sidebarWidth));
  const savedResultsHeight = Number(localStorage.getItem(layoutStorageKeys.resultsHeight));
  if (savedSidebarWidth) setSidebarWidth(savedSidebarWidth);
  if (savedResultsHeight) setResultsHeight(savedResultsHeight);
  const isAgentRouteEntry = new URLSearchParams(window.location.search).get("route") === "agent";
  setSidebarCollapsed(
    isAgentRouteEntry ? localStorage.getItem(layoutStorageKeys.sidebarCollapsed) === "true" : false,
    { persist: false }
  );
  setResultsCollapsed(localStorage.getItem(layoutStorageKeys.resultsCollapsed) === "true");

  sidebarResizer.addEventListener("pointerdown", event => {
    if (shell.classList.contains("sidebar-collapsed")) return;
    event.preventDefault();
    startDrag(event, "sidebar", nextEvent => {
      setSidebarWidth(nextEvent.clientX);
    });
  });

  resultsResizer.addEventListener("pointerdown", event => {
    if (mapWrap.classList.contains("results-collapsed")) return;
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = getResultsHeight();
    startDrag(event, "results", nextEvent => {
      setResultsHeight(startHeight + startY - nextEvent.clientY);
    });
  });

  closeSidebar.addEventListener("click", () => setSidebarCollapsed(true));
  openSidebar.addEventListener("click", () => setSidebarCollapsed(false));
  closeResults.addEventListener("click", () => setResultsCollapsed(true));
  openResults.addEventListener("click", () => setResultsCollapsed(false));

  window.addEventListener("resize", () => {
    setSidebarWidth(getSidebarWidth());
    setResultsHeight(getResultsHeight());
    scheduleMapResize();
  });
}

function startDrag(event, className, onMove) {
  document.body.classList.add(`dragging-${className}`);
  event.currentTarget.setPointerCapture(event.pointerId);
  const target = event.currentTarget;
  const move = nextEvent => {
    onMove(nextEvent);
    scheduleMapResize();
  };
  const stop = () => {
    document.body.classList.remove(`dragging-${className}`);
    target.removeEventListener("pointermove", move);
    target.removeEventListener("pointerup", stop);
    target.removeEventListener("pointercancel", stop);
    scheduleMapResize();
  };
  target.addEventListener("pointermove", move);
  target.addEventListener("pointerup", stop);
  target.addEventListener("pointercancel", stop);
}

function setSidebarWidth(width) {
  const shell = document.getElementById("layout");
  const maxWidth = Math.min(560, Math.max(320, window.innerWidth * 0.45));
  const next = clamp(width, 300, maxWidth);
  shell.style.setProperty("--sidebar-width", `${Math.round(next)}px`);
  localStorage.setItem(layoutStorageKeys.sidebarWidth, String(Math.round(next)));
}

function getSidebarWidth() {
  return Number.parseFloat(getComputedStyle(document.getElementById("layout")).getPropertyValue("--sidebar-width")) || 320;
}

function setResultsHeight(height) {
  const shell = document.getElementById("layout");
  const maxHeight = Math.min(520, Math.max(180, window.innerHeight * 0.58));
  const next = clamp(height, 180, maxHeight);
  shell.style.setProperty("--results-height", `${Math.round(next)}px`);
  localStorage.setItem(layoutStorageKeys.resultsHeight, String(Math.round(next)));
}

function getResultsHeight() {
  return Number.parseFloat(getComputedStyle(document.getElementById("layout")).getPropertyValue("--results-height")) || 300;
}

function setSidebarCollapsed(collapsed, options = {}) {
  const persist = options.persist !== false;
  const shell = document.getElementById("layout");
  shell.classList.toggle("sidebar-collapsed", collapsed);
  document.getElementById("openSidebar").hidden = !collapsed;
  if (persist) {
    localStorage.setItem(layoutStorageKeys.sidebarCollapsed, String(collapsed));
  }
  scheduleMapResize();
}

function setResultsCollapsed(collapsed) {
  const mapWrap = document.querySelector(".map-wrap");
  mapWrap.classList.toggle("results-collapsed", collapsed);
  document.getElementById("openResults").hidden = !collapsed;
  localStorage.setItem(layoutStorageKeys.resultsCollapsed, String(collapsed));
  scheduleMapResize();
}

function scheduleMapResize() {
  const resize = () => {
    if (map && typeof map.resize === "function") {
      map.resize();
    }
  };
  window.requestAnimationFrame(() => {
    resize();
    window.requestAnimationFrame(resize);
  });
  window.setTimeout(resize, 80);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function parseLngLat(value) {
  if (!value) return null;
  const lng = typeof value.getLng === "function" ? value.getLng() : Number(value.lng ?? value[0]);
  const lat = typeof value.getLat === "function" ? value.getLat() : Number(value.lat ?? value[1]);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
  return { lng, lat };
}

function isProbablyShanghai(lng, lat) {
  return lng >= 120.8 && lng <= 122.3 && lat >= 30.6 && lat <= 31.95;
}

function normalizeShanghaiAddress(value) {
  const text = String(value || "").trim();
  if (!text) return "上海";
  if (/上海|Shanghai/i.test(text)) return text;
  return `上海 ${text}`;
}

function formatPoiAddress(poi) {
  const parts = [poi.district, poi.address].filter(part => typeof part === "string" && part.trim());
  const address = parts.join(" ");
  if (address) return normalizeShanghaiAddress(`${address} ${poi.name || ""}`.trim());
  return normalizeShanghaiAddress(poi.name || document.getElementById("workplace").value);
}

function firstPoiFromPlaceSearch(result) {
  const poiList = result && result.poiList ? result.poiList : null;
  const pois = poiList && Array.isArray(poiList.pois) ? poiList.pois : [];
  return pois[0] || null;
}

function firstLocationFromGeocode(result) {
  const geocodes = result && Array.isArray(result.geocodes) ? result.geocodes : [];
  return geocodes.length ? parseLngLat(geocodes[0].location) : null;
}

function firstPoiFromReverseGeocode(regeocode) {
  const pois = regeocode && Array.isArray(regeocode.pois) ? regeocode.pois : [];
  return pois[0] || null;
}

function shortAddress(address) {
  const text = String(address || "").replace(/^上海市?/, "").trim();
  if (!text) return "地图选点";
  return text;
}

function renderMarkers(geojson) {
  const AMap = AMapApi || window.AMap;
  if (!map || !AMap || !geojson) return;
  clearMap();
  geojson.features.forEach(feature => {
    const [lng, lat] = feature.geometry.coordinates;
    const p = feature.properties;
    const marker = new AMap.Marker({
      position: [lng, lat],
      title: p.title,
      ...(p.marker_label
        ? {
            content: `<div class="rent-marker">${escapeHtml(p.marker_label)}</div>`,
            offset: new AMap.Pixel(-15, -15),
            zIndex: 110
          }
        : { label: { content: `${Math.round(p.score)}`, direction: "top" } })
    });
    marker.on("click", () => {
      const item = latestResults.find(result => String(result.id) === String(p.id));
      const best = item ? bestDisplayRoute(item) : null;
      const commuteText = best
        ? formatCommute(best)
        : formatCommute({ duration_min: p.commute_min, mode: selectedCommuteMode(), route_status: p.commute_min ? "ok" : "unavailable" });
      const html = `<strong>${escapeHtml(p.title)}</strong><br/>${escapeHtml(selectedRoomLabel())}参考租金 ${escapeHtml(formatCurrency(p.rent_monthly))}<br/>${escapeHtml(commuteText)}`;
      new AMap.InfoWindow({ content: html }).open(map, [lng, lat]);
    });
    map.add(marker);
    markers.push(marker);
    markersById.set(String(p.id), marker);
  });
  if (markers.length) map.setFitView(workMarker ? [...markers, workMarker] : markers);
}

function renderRoutes(geojson) {
  const AMap = AMapApi || window.AMap;
  if (!map || !AMap || !geojson) return;
  geojson.features.forEach(feature => {
    const path = feature.geometry.coordinates.map(pair => [pair[0], pair[1]]);
    const line = new AMap.Polyline({ path, strokeColor: "#0f766e", strokeWeight: 5, strokeOpacity: 0.8 });
    map.add(line);
    polylines.push(line);
  });
}

function renderResultCards(results) {
  const root = document.getElementById("cards");
  root.innerHTML = "";
  if (!results.length) {
    renderPendingState("暂无候选结果", "当前条件下没有可展示的上海候选项。");
    return;
  }
  results.forEach(item => {
    const card = document.createElement("article");
    card.className = "card";
    const best = bestDisplayRoute(item);
    const typeLabel = item.item_type === "community" ? "小区" : (item.item_type === "area" ? "区域" : "房源");
    card.innerHTML = `
      <h3>${escapeHtml(item.title)}</h3>
      <div class="meta">类型：${escapeHtml(typeLabel)}｜${escapeHtml(item.district || "")}</div>
      <div class="meta">${escapeHtml(selectedRoomLabel())}参考租金：${escapeHtml(formatCurrency(item.rent_monthly))}</div>
      <div class="meta">${escapeHtml(formatCommute(best))}</div>
      <button class="route-button" type="button" data-item-id="${escapeHtml(item.id)}"><span class="button-content"><svg class="ui-icon"><use href="#icon-route"></use></svg>生成路径</span></button>
    `;
    card.dataset.itemId = String(item.id);
    card.querySelector(".route-button").addEventListener("click", event => {
      event.stopPropagation();
      renderRouteForItem(String(item.id));
    });
    root.appendChild(card);
  });
}

function loadAgentRouteSelection() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("route") !== "agent") return;
  setSidebarCollapsed(true, { persist: false });
  const raw = sessionStorage.getItem(agentRouteStorageKey);
  if (!raw) {
    showStatusMessage("没有找到从对话页带来的路线数据。");
    return;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (error) {
    showStatusMessage("路线数据读取失败，请回到对话页重新打开。");
    return;
  }
  applyAgentRouteSelection(payload);
}

function applyAgentRouteSelection(payload) {
  const item = normalizeAgentRouteItem(payload.item, payload.route);
  if (!item || !Number.isFinite(Number(item.lng)) || !Number.isFinite(Number(item.lat))) {
    showStatusMessage("这个候选缺少可用坐标，无法在地图上定位。");
    return;
  }
  const summary = payload.request_summary || {};
  setFormValue("budget", summary.budget_monthly);
  setFormValue("rooms", summary.rooms);
  setFormValue("commute", summary.max_commute_min);
  const best = bestDisplayRoute(item);
  const mode = best && best.mode ? best.mode : (Array.isArray(summary.commute_modes) ? summary.commute_modes[0] : null);
  setSelectValue("mode", mode);

  latestResults = [item];
  selectedRouteItemId = String(item.id);
  setResultsCollapsed(false);
  renderResultCards(latestResults);

  const work = normalizeAgentWork(payload.work, best);
  if (work) {
    selectedWorkAnchor = work;
    suppressWorkplaceInput = true;
    document.getElementById("workplace").value = shortAddress(work.address || work.label || "工作地点");
    window.setTimeout(() => { suppressWorkplaceInput = false; }, 0);
    setWorkplaceStatus(`已从对话页带入：${work.address || work.label}`);
  }

  if (!map || !(AMapApi || window.AMap)) {
    showStatusMessage("地图底图暂不可用，已保留候选卡片。");
    return;
  }

  removeWorkMarker();
  clearMap();
  if (work) updateWorkMarker(work);
  renderMarkers({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [Number(item.lng), Number(item.lat)] },
        properties: {
          id: item.id,
          title: item.title,
          item_type: item.item_type,
          score: item.total_score || 0,
          rent_monthly: item.rent_monthly,
          district: item.district,
          commute_min: best ? best.duration_min : null,
          marker_label: "租"
        }
      }
    ]
  });
  renderRouteForItem(String(item.id));
}

function normalizeAgentRouteItem(item, route) {
  if (!item) return null;
  const routes = Array.isArray(item.commute_routes) ? [...item.commute_routes] : [];
  if (route && !routes.some(candidate => JSON.stringify(candidate) === JSON.stringify(route))) {
    routes.unshift(route);
  }
  return {
    ...item,
    id: String(item.id || item.title || Date.now()),
    item_type: item.item_type || "community",
    commute_routes: routes
  };
}

function normalizeAgentWork(work, route) {
  const coords = route && route.route_geojson && Array.isArray(route.route_geojson.coordinates)
    ? route.route_geojson.coordinates
    : [];
  const routeEnd = coords.length ? coords[coords.length - 1] : null;
  const lng = work && Number.isFinite(Number(work.lng)) ? Number(work.lng) : (routeEnd ? Number(routeEnd[0]) : null);
  const lat = work && Number.isFinite(Number(work.lat)) ? Number(work.lat) : (routeEnd ? Number(routeEnd[1]) : null);
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || !isProbablyShanghai(lng, lat)) return null;
  return {
    name: work && work.label ? work.label : "工作地点",
    label: work && work.label ? work.label : "工作地点",
    address: work && work.address ? work.address : "工作地点",
    lng,
    lat,
    source: "agent_route"
  };
}

function setFormValue(id, value) {
  if (value === null || value === undefined || value === "") return;
  const element = document.getElementById(id);
  if (element) element.value = value;
}

function setSelectValue(id, value) {
  if (!value) return;
  const element = document.getElementById(id);
  if (!element) return;
  if ([...element.options].some(option => option.value === String(value))) {
    element.value = String(value);
  }
}

function renderRouteForItem(itemId) {
  const AMap = AMapApi || window.AMap;
  if (!map || !AMap) {
    showStatusMessage("地图暂不可用，无法绘制通勤路径。");
    return;
  }
  const item = latestResults.find(result => String(result.id) === String(itemId));
  if (!item) {
    showStatusMessage("没有找到这个候选项。");
    return;
  }
  const route = bestDrawableRoute(item);
  clearRoutes();
  if (!route) {
    selectedRouteItemId = null;
    updateSelectedCard();
    showStatusMessage("这个候选项暂无可绘制的通勤路径。");
    return;
  }
  const path = route.route_geojson.coordinates.map(pair => [pair[0], pair[1]]);
  const line = new AMap.Polyline({
    path,
    strokeColor: "#0f766e",
    strokeWeight: 6,
    strokeOpacity: 0.9,
    lineJoin: "round",
    lineCap: "round"
  });
  map.add(line);
  polylines.push(line);
  selectedRouteItemId = String(itemId);
  updateSelectedCard();
  clearStatusMessage();
  const selectedMarker = markersById.get(String(itemId));
  const fitItems = [line];
  if (selectedMarker) fitItems.push(selectedMarker);
  if (workMarker) fitItems.push(workMarker);
  map.setFitView(fitItems);
}

function bestDrawableRoute(item) {
  const routes = Array.isArray(item.commute_routes) ? item.commute_routes : [];
  return routes
    .filter(route => (
      route.route_status === "ok"
      && route.route_geojson
      && route.route_geojson.type === "LineString"
      && Array.isArray(route.route_geojson.coordinates)
      && route.route_geojson.coordinates.length > 1
    ))
    .sort((a, b) => (a.duration_min || Number.POSITIVE_INFINITY) - (b.duration_min || Number.POSITIVE_INFINITY))[0] || null;
}

function bestDisplayRoute(item) {
  const routes = Array.isArray(item.commute_routes) ? item.commute_routes : [];
  return routes
    .filter(route => route.route_status === "ok" && route.duration_min !== null && route.duration_min !== undefined)
    .sort((a, b) => Number(a.duration_min) - Number(b.duration_min))[0] || routes[0] || null;
}

function formatCommute(route) {
  if (!route) return "预计通勤：路线暂不可用";
  if (route.route_status !== "ok" || route.duration_min === null || route.duration_min === undefined) {
    return "预计通勤：路线暂不可用";
  }
  return `预计通勤：${formatMinutes(route.duration_min)} 分钟（${commuteModeLabel(route.mode)}）`;
}

function formatMinutes(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return String(Math.round(number));
}

function selectedCommuteMode() {
  return document.getElementById("mode").value;
}

function commuteModeLabel(mode) {
  const labels = {
    transit: "公交/地铁",
    driving: "驾车",
    walking: "步行",
    bicycling: "骑行",
    electrobike: "电动车"
  };
  return labels[mode] || labels[selectedCommuteMode()] || "通勤";
}

function updateSelectedCard() {
  document.querySelectorAll(".card").forEach(card => {
    const active = selectedRouteItemId !== null && card.dataset.itemId === selectedRouteItemId;
    card.classList.toggle("card-active", active);
    const button = card.querySelector(".route-button");
    if (button) {
      button.textContent = active ? "已生成路径" : "生成路径";
    }
  });
}

function selectedRoomLabel() {
  const room = document.getElementById("rooms").value;
  if (room === "2") return "二室";
  if (room === "3") return "三室";
  return "一室";
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `${Number(value).toLocaleString("zh-CN")} 元/月`;
}

function showStatusMessage(message) {
  const warning = document.getElementById("warning");
  warning.textContent = message;
  warning.hidden = false;
}

function clearStatusMessage() {
  const warning = document.getElementById("warning");
  warning.textContent = "";
  warning.hidden = true;
}

function renderPendingState(title = "待选候选", text = "推荐结果将在这里形成候选卡片。") {
  const root = document.getElementById("cards");
  root.innerHTML = `
    <section class="empty-state">
      <div class="empty-copy">
        <div class="eyebrow">RESULTS</div>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(text)}</p>
      </div>
      ${placeholderCard("预算匹配")}
      ${placeholderCard("通勤计算")}
      ${placeholderCard("风险提示")}
    </section>
  `;
}

function renderLoadingState() {
  const root = document.getElementById("cards");
  root.innerHTML = `
    <section class="empty-state loading">
      <div class="empty-copy">
        <div class="eyebrow">SCORING</div>
        <h2>正在生成候选</h2>
        <p>正在核验上海范围、查询通勤并计算综合分。</p>
      </div>
      ${placeholderCard("预算匹配")}
      ${placeholderCard("通勤计算")}
      ${placeholderCard("地图图层")}
    </section>
  `;
}

function placeholderCard(label) {
  return `
    <article class="placeholder-card">
      <div class="placeholder-title"></div>
      <div class="placeholder-line medium"></div>
      <div class="placeholder-line"></div>
      <div class="placeholder-line short"></div>
      <span class="placeholder-chip">${escapeHtml(label)}</span>
    </article>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

document.getElementById("recommend").addEventListener("click", recommend);
initWorkplaceInput();
initResizableLayout();
renderPendingState();
clearStatusMessage();
initMap()
  .then(loadAgentRouteSelection)
  .catch(() => {
    showStatusMessage("地图初始化失败，请检查高德 JS Key。");
    loadAgentRouteSelection();
  });
