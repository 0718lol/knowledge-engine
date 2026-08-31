"""DeepSeek-backed technical strategy agent client.

The API key is read only from DEEPSEEK_API_KEY. No credential is persisted.
"""
import json
import os
from urllib import error, request


DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


class StrategyAgentError(RuntimeError):
    """A user-safe error raised when the strategy agent cannot complete."""


def configured():
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def _decode_error(exc):
    if isinstance(exc, error.HTTPError):
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            message = detail.get("error", {}).get("message") or detail.get("message")
            if message:
                return f"DeepSeek 请求失败：{message}"
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        return f"DeepSeek 请求失败（HTTP {exc.code}）"
    if isinstance(exc, error.URLError):
        return "无法连接 DeepSeek，请检查网络或代理设置"
    return "技术战略 Agent 暂时不可用"


def complete(messages, *, max_tokens=2400, timeout=45):
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise StrategyAgentError("尚未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        "messages": messages,
        "thinking": {"type": "disabled"},
        "stream": False,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise StrategyAgentError(_decode_error(exc)) from exc
    try:
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise StrategyAgentError("模型返回格式不完整，未生成可用战略简报") from exc
    if not isinstance(result, dict):
        raise StrategyAgentError("模型返回的战略简报不是对象格式")
    return result


def analyze(question, context):
    system = """你是技术战略分析 Agent，服务对象是企业技术战略人员。
只使用输入中的事实，不要编造来源或公司数据。把不确定信息明确标注为待验证。
输出必须是 JSON 对象，字段固定为：executive_summary、decision、options、evidence_gaps、risks、signals、next_actions。
options 是数组，每项包含 name、fit、advantages、tradeoffs、evidence_level。
risks、signals、next_actions 是字符串数组。结论要面向技术投资、路线选择和执行，不要写成学术综述。"""
    user = {
        "question": question,
        "local_knowledge": context,
        "output_requirements": {
            "decision": "给出条件化建议，不要伪装成确定事实",
            "evidence_gaps": "列出下一步必须补齐的证据",
            "signals": "列出未来需要持续跟踪的外部信号",
        },
    }
    return complete([
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ])
