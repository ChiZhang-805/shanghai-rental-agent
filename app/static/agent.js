const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const routeStorageKey = "rentAgent.agentRouteSelection";
let latestRecommendationData = null;

const starters = [
  "我在盛大全球研发中心上班，预算5500人民币/月，想在附近租一间一室的屋子，预计步行通勤在45分钟以内，请帮我推荐租哪里比较合适",
  "我在漕河泾上班，预算6000人民币/月，想找通勤方便的一室小区",
  "我看到小红书说通勤和地铁很重要，预算也要稳，帮我提取选房标准"
];

function init() {
  appendMessage("agent", "您好！我是你的智能租房 Agent 小驰！您可以直接描述需求，我会判断您的意图，查询上海房源及对应的区域数据，为您推荐租房信息。");
  renderPlaceholderCards();
  const quick = document.createElement("div");
  quick.className = "quick";
  starters.forEach(text => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.addEventListener("click", () => {
      promptInput.value = text;
      promptInput.focus();
    });
    quick.appendChild(button);
  });
  messages.appendChild(quick);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text) return;
  appendMessage("user", text);
  promptInput.value = "";
  sendButton.disabled = true;
  const pending = appendMessage("agent", "正在理解你的需求并查阅上海候选数据...");
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });
    const data = await response.json();
    pending.remove();
    if (!response.ok) {
      appendMessage("agent", data.detail || "请求失败。");
      return;
    }
    appendMessage("agent", data.answer || "已完成。");
    renderDetails(data);
  } catch (error) {
    pending.remove();
    appendMessage("agent", "服务暂时不可用，请稍后再试。");
  } finally {
    sendButton.disabled = false;
    promptInput.focus();
  }
});

promptInput.addEventListener("keydown", event => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    form.requestSubmit();
  }
});

function appendMessage(role, text) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  const avatar = document.createElement("img");
  avatar.className = "avatar";
  avatar.src = role === "user" ? "/static/Me_icon.png" : "/static/agent__icon.png";
  avatar.alt = role === "user" ? "你的头像" : "小驰头像";
  const content = document.createElement("div");
  content.className = "message-content";
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role === "user" ? "你" : "小驰";
  const body = document.createElement("div");
  body.className = "bubble";
  body.textContent = text;
  content.append(label, body);
  item.append(avatar, content);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function renderDetails(response) {
  const data = response.data || {};
  const results = data.results || [];
  latestRecommendationData = data;
  renderResults(results);
}

function renderResults(results) {
  const root = document.getElementById("results");
  root.replaceChildren();
  if (!results.length) {
    renderPlaceholderCards();
    return;
  }
  results.slice(0, 6).forEach(item => {
    const card = document.createElement("article");
    card.className = "result";
    const title = document.createElement("h2");
    title.textContent = item.title || item.id;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = [
      item.district || "上海",
      formatItemTypeLabel(item.item_type),
      formatDataSourceLabel(item)
    ].join(" | ");
    const rent = document.createElement("div");
    rent.className = "score";
    rent.textContent = item.rent_monthly ? `参考租金：${item.rent_monthly} 元/月` : "参考租金：暂无";
    const commute = document.createElement("div");
    commute.className = "commute";
    commute.textContent = formatCommute(item.commute_routes || []);
    const actions = document.createElement("div");
    actions.className = "result-actions";
    const mapButton = document.createElement("button");
    mapButton.className = "map-route-button";
    mapButton.type = "button";
    mapButton.title = "在地图查看路线";
    mapButton.setAttribute("aria-label", `在地图查看${item.title || "候选"}的路线`);
    mapButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="6" cy="6" r="2.4"></circle>
        <circle cx="18" cy="18" r="2.4"></circle>
        <path d="M8.5 6H14a4 4 0 0 1 0 8h-4a4 4 0 0 0 0 8h5.5"></path>
      </svg>
    `;
    mapButton.addEventListener("click", () => openRouteInMap(item));
    actions.appendChild(mapButton);
    card.append(title, meta, rent, commute, actions);
    root.appendChild(card);
  });
}

function openRouteInMap(item) {
  const route = bestRouteForMap(item);
  const routeCoords = route && route.route_geojson && Array.isArray(route.route_geojson.coordinates)
    ? route.route_geojson.coordinates
    : [];
  const requestSummary = latestRecommendationData && latestRecommendationData.request_summary
    ? latestRecommendationData.request_summary
    : {};
  const anchor = Array.isArray(requestSummary.anchors) ? requestSummary.anchors[0] : null;
  const routeEnd = routeCoords.length ? routeCoords[routeCoords.length - 1] : null;
  const work = {
    label: anchor && anchor.label ? anchor.label : "工作地点",
    address: anchor && anchor.address ? anchor.address : "工作地点",
    lng: anchor && Number.isFinite(Number(anchor.lng)) ? Number(anchor.lng) : (routeEnd ? Number(routeEnd[0]) : null),
    lat: anchor && Number.isFinite(Number(anchor.lat)) ? Number(anchor.lat) : (routeEnd ? Number(routeEnd[1]) : null)
  };
  const payload = {
    source: "agent",
    createdAt: Date.now(),
    item,
    route,
    work,
    request_summary: requestSummary
  };
  sessionStorage.setItem(routeStorageKey, JSON.stringify(payload));
  window.location.href = "/map?route=agent";
}

function bestRouteForMap(item) {
  const routes = Array.isArray(item.commute_routes) ? item.commute_routes : [];
  return routes
    .filter(route => (
      route.route_status === "ok"
      && route.route_geojson
      && route.route_geojson.type === "LineString"
      && Array.isArray(route.route_geojson.coordinates)
      && route.route_geojson.coordinates.length > 1
    ))
    .sort((a, b) => Number(a.duration_min || Infinity) - Number(b.duration_min || Infinity))[0]
    || routes.find(route => route.route_status === "ok")
    || routes[0]
    || null;
}

function formatItemTypeLabel(type) {
  if (type === "community") return "小区";
  if (type === "area") return "区域";
  if (type === "listing") return "房源";
  return "候选";
}

function formatDataSourceLabel(item) {
  if (item.item_type === "community") return "高德候选";
  if (item.item_type === "area") return "区域参考";
  if (item.item_type === "listing") return "真实房源";
  return "候选";
}

function renderPlaceholderCards() {
  const root = document.getElementById("results");
  root.replaceChildren();
  for (let index = 0; index < 4; index += 1) {
    const card = document.createElement("article");
    card.className = "result placeholder-card";
    const title = document.createElement("h2");
    title.textContent = "待填写";
    const lineA = document.createElement("div");
    lineA.className = "placeholder-line short";
    const lineB = document.createElement("div");
    lineB.className = "placeholder-line";
    const lineC = document.createElement("div");
    lineC.className = "placeholder-line medium";
    card.append(title, lineA, lineB, lineC);
    root.appendChild(card);
  }
}

function formatCommute(routes) {
  if (!routes.length) return "通勤：未计算";
  const best = routes.find(route => route.route_status === "ok" && route.duration_min !== null) || routes[0];
  if (best.route_status === "ok") {
    const minutes = Math.round(Number(best.duration_min));
    return `通勤：${formatModeLabel(best.mode)}约 ${minutes} 分钟`;
  }
  return "通勤：路线暂不可用";
}

function formatModeLabel(mode) {
  const labels = {
    transit: "公交地铁",
    driving: "驾车",
    walking: "步行",
    bicycling: "骑行",
    electrobike: "电动车"
  };
  return labels[mode] || "通勤";
}

init();
