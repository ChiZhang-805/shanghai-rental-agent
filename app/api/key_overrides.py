from fastapi import Request


HEADER_TO_SETTING_FIELD = {
    "x-openai-api-key": "openai_api_key",
    "x-amap-web-service-key": "amap_web_service_key",
    "x-amap-js-api-key": "amap_js_api_key",
    "x-amap-js-security-code": "amap_js_security_code",
}


def settings_overrides_from_headers(request: Request | None) -> dict[str, str]:
    if request is None:
        return {}
    overrides: dict[str, str] = {}
    for header_name, field_name in HEADER_TO_SETTING_FIELD.items():
        value = request.headers.get(header_name)
        if value and value.strip():
            overrides[field_name] = value.strip()
    return overrides


def request_settings_overrides(request: Request) -> dict[str, str]:
    return settings_overrides_from_headers(request)
