from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
from nonebot import logger

# 内置工具名，技能不能占用
RESERVED_TOOL_NAMES = {
    "search_knowledge_base",
    "web_search",
    "send_voice",
    "send_followup",
}

_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
_DEFAULT_PARAMETERS = {"type": "object", "properties": {}}
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def parse_tool_config(content: str) -> dict[str, Any]:
    """解析并校验 HTTP 工具配置，返回规范化后的配置。"""
    try:
        config = json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"工具配置不是合法 JSON: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("工具配置必须是 JSON 对象")

    method = str(config.get("method") or "GET").upper()
    if method not in _ALLOWED_METHODS:
        raise ValueError(f"不支持的请求方法: {method}")

    url = str(config.get("url") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("请求地址必须以 http:// 或 https:// 开头")

    headers = config.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError("headers 必须是 JSON 对象")

    parameters = config.get("parameters")
    if parameters is None:
        parameters = dict(_DEFAULT_PARAMETERS)
    if not isinstance(parameters, dict):
        raise ValueError("parameters 必须是 JSON Schema 对象")
    if parameters.get("type", "object") != "object":
        raise ValueError("parameters.type 必须是 object")
    properties = parameters.get("properties") or {}
    if not isinstance(properties, dict):
        raise ValueError("parameters.properties 必须是 JSON 对象")
    required = parameters.get("required")
    if required is not None and not isinstance(required, list):
        raise ValueError("parameters.required 必须是数组")

    try:
        timeout = float(config.get("timeout", 15))
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout 必须是数字") from exc
    if timeout <= 0 or timeout > 120:
        raise ValueError("timeout 需在 1~120 秒之间")

    try:
        max_length = int(config.get("max_length", 2000))
    except (TypeError, ValueError) as exc:
        raise ValueError("max_length 必须是整数") from exc
    if max_length < 200 or max_length > 8000:
        raise ValueError("max_length 需在 200~8000 之间")

    return {
        **config,
        "method": method,
        "url": url,
        "headers": headers,
        "parameters": {**parameters, "type": "object", "properties": properties},
        "timeout": timeout,
        "max_length": max_length,
    }


def _substitute(value: Any, arguments: dict[str, Any]) -> Any:
    """把配置里的 {参数名} 占位符替换为 AI 传入的参数。"""
    if isinstance(value, str):
        exact = _PLACEHOLDER.fullmatch(value)
        if exact:
            key = exact.group(1)
            if key in arguments:
                return arguments[key]
            return value
        return _PLACEHOLDER.sub(
            lambda match: str(arguments.get(match.group(1), match.group(0))),
            value,
        )
    if isinstance(value, dict):
        return {key: _substitute(item, arguments) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, arguments) for item in value]
    return value


def _coerce_arguments(arguments: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """按参数 schema 做一次宽松的类型转换。"""
    properties = parameters.get("properties") or {}
    result = dict(arguments)
    for key, spec in properties.items():
        if key not in result or not isinstance(spec, dict):
            continue
        expected = spec.get("type")
        raw = result[key]
        if not isinstance(raw, str):
            continue
        try:
            if expected in ("number", "integer"):
                number = float(raw)
                result[key] = int(number) if expected == "integer" else number
            elif expected == "boolean":
                result[key] = raw.strip().lower() in ("true", "1", "yes", "y", "是")
        except (TypeError, ValueError):
            continue
    return result


class SkillManager:
    """读取数据库中的技能，并负责提示词拼接与 HTTP 工具执行。"""

    def __init__(self, db):
        self.db = db

    def _allowed(self, group_id: Optional[int]) -> list[dict]:
        if not self.db:
            return []
        rows = self.db.get_all_skills()
        result: list[dict] = []
        for row in rows:
            if not row.get("enabled"):
                continue
            scope = row.get("scope") or "global"
            if scope == "global":
                result.append(row)
            elif scope == "group" and group_id is not None and row.get("group_id") == group_id:
                result.append(row)
        return result

    @staticmethod
    def _is_allowed(skill: dict, group_id: Optional[int]) -> bool:
        if not skill.get("enabled"):
            return False
        scope = skill.get("scope") or "global"
        if scope == "global":
            return True
        return group_id is not None and skill.get("group_id") == group_id

    def build_prompt(self, group_id: Optional[int] = None) -> str:
        """把启用中的提示词型技能拼成系统提示词片段。"""
        skills = [row for row in self._allowed(group_id) if row.get("type") == "prompt"]
        blocks: list[str] = []
        for row in skills:
            content = (row.get("content") or "").strip()
            if not content:
                continue
            blocks.append(f"### {row['title']}\n{content}")
        if not blocks:
            return ""
        return (
            "\n\n## 可用技能\n"
            "下面是你可以参考的技能说明。遇到对应场景时，请按技能说明处理：\n\n"
            + "\n\n".join(blocks)
        )

    def build_tools(self, group_id: Optional[int] = None) -> list[dict]:
        """把启用中的 HTTP 工具型技能转换成 OpenAI tools 定义。"""
        tools: list[dict] = []
        for row in self._allowed(group_id):
            if row.get("type") != "tool":
                continue
            name = row.get("name") or ""
            if not name or name in RESERVED_TOOL_NAMES:
                continue
            try:
                config = parse_tool_config(row.get("content") or "")
            except ValueError as exc:
                logger.warning(f"技能 {name} 配置无效，已跳过: {exc}")
                continue
            description = (row.get("description") or row.get("title") or "").strip()
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description or row["title"],
                        "parameters": config["parameters"],
                    },
                }
            )
        return tools

    async def execute(
        self,
        name: str,
        arguments: Optional[dict[str, Any]],
        group_id: Optional[int] = None,
    ) -> str:
        """执行 AI 发起的技能调用，返回给模型参考的文本结果。"""
        if not self.db:
            return f"技能 {name} 执行失败：数据库未初始化"
        skill = self.db.get_skill_by_name(name)
        if not skill:
            return f"技能 {name} 不存在"
        if not self._is_allowed(skill, group_id):
            return f"技能 {name} 未启用或不适用于当前会话"

        try:
            config = parse_tool_config(skill.get("content") or "")
        except ValueError as exc:
            logger.warning(f"技能 {name} 配置无效: {exc}")
            return f"技能 {skill['title']} 配置无效：{exc}"

        raw_arguments = arguments if isinstance(arguments, dict) else {}
        args = _coerce_arguments(raw_arguments, config["parameters"])
        url = _substitute(config["url"], args)
        headers = _substitute(config.get("headers") or {}, args)
        body = config.get("body")
        if body is not None:
            body = _substitute(body, args)

        request_kwargs: dict[str, Any] = {}
        if headers:
            request_kwargs["headers"] = {
                str(key): str(value) for key, value in headers.items()
            }
        if config["method"] not in ("GET", "HEAD") and body is not None:
            if isinstance(body, (dict, list)):
                request_kwargs["json"] = body
            else:
                request_kwargs["content"] = str(body)

        logger.info(f"执行技能 {name} ({config['method']} {url})")
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.request(
                    config["method"],
                    str(url),
                    timeout=config["timeout"],
                    **request_kwargs,
                )
                response.raise_for_status()
                text = response.text or ""
        except Exception as exc:
            logger.warning(f"技能 {name} 调用失败: {exc}")
            return f"技能 {skill['title']} 调用失败：{exc}"

        max_length = int(config["max_length"])
        if len(text) > max_length:
            text = text[:max_length] + "\n...(结果已截断)"
        return f"【技能 {skill['title']} 返回】\n{text}"
