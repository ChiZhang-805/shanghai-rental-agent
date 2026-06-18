(function () {
  const storageKey = "rentAgent.apiKeys";
  const fields = {
    openaiApiKey: "OpenAI API Key",
    amapWebServiceKey: "高德 Web 服务 Key",
    amapJsApiKey: "高德 JS API Key",
    amapJsSecurityCode: "高德 JS 安全密钥"
  };
  const headerNames = {
    openaiApiKey: "X-OpenAI-API-Key",
    amapWebServiceKey: "X-AMAP-Web-Service-Key",
    amapJsApiKey: "X-AMAP-JS-API-Key",
    amapJsSecurityCode: "X-AMAP-JS-Security-Code"
  };

  function load() {
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function save(values) {
    const cleaned = {};
    Object.keys(fields).forEach(key => {
      const value = values[key];
      if (typeof value === "string" && value.trim()) {
        cleaned[key] = value.trim();
      }
    });
    localStorage.setItem(storageKey, JSON.stringify(cleaned));
    window.dispatchEvent(new CustomEvent("rent-agent-keys-saved", { detail: cleaned }));
    return cleaned;
  }

  function headers() {
    const values = load();
    const result = {};
    Object.keys(headerNames).forEach(key => {
      if (values[key]) {
        result[headerNames[key]] = values[key];
      }
    });
    return result;
  }

  function amapClientConfig() {
    const values = load();
    const fallback = window.APP_CONFIG || {};
    const securityFallback = window._AMapSecurityConfig || {};
    return {
      key: values.amapJsApiKey || fallback.amapKey || "",
      securityCode: values.amapJsSecurityCode || securityFallback.securityJsCode || ""
    };
  }

  function mountPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const values = load();
    const inputs = panel.querySelectorAll("[data-key-field]");
    inputs.forEach(input => {
      const key = input.dataset.keyField;
      input.value = values[key] || "";
      input.type = "password";
      input.autocomplete = "off";
    });

    panel.querySelectorAll("[data-key-toggle]").forEach(button => {
      button.addEventListener("click", () => {
        const key = button.dataset.keyToggle;
        const input = panel.querySelector(`[data-key-field="${key}"]`);
        if (!input) return;
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.classList.toggle("is-visible", !showing);
        button.setAttribute("aria-label", `${showing ? "显示" : "隐藏"}${fields[key] || "Key"}`);
      });
    });

    const saveButton = panel.querySelector("[data-key-save]");
    if (saveButton) {
      saveButton.addEventListener("click", () => {
        const next = {};
        inputs.forEach(input => {
          next[input.dataset.keyField] = input.value;
        });
        save(next);
        setStatus(panel, "");
      });
    }
  }

  function setStatus(panel, text) {
    const status = panel.querySelector("[data-key-status]");
    if (!status) return;
    status.textContent = text;
    window.clearTimeout(status._clearTimer);
    status._clearTimer = window.setTimeout(() => {
      status.textContent = "";
    }, 2600);
  }

  window.RentAgentKeys = {
    load,
    save,
    headers,
    amapClientConfig,
    mountPanel
  };
})();
