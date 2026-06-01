"""AI 视觉分析器：调用 Moonshot Kimi 视觉大模型识别图纸色号。"""

import base64
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .color_chart import ColorChart, get_chart


def _image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _normalize_mard_code(code: str) -> str:
    """统一 Mard 色号格式，如 A1 -> A01, ZG1 -> ZG1"""
    m = re.match(r'^([A-Za-z]+)(\d+)$', code)
    if not m:
        return code.upper()
    prefix, num = m.groups()
    prefix = prefix.upper()
    num = int(num)
    if len(prefix) == 1:
        return f"{prefix}{num:02d}"
    return f"{prefix}{num}"


def _parse_vision_response(text: str, valid_codes: set) -> List[Tuple[str, Optional[int], float, str]]:
    """
    解析 Kimi 返回的色号清单文本。
    返回: [(code, quantity, confidence, raw_line), ...]
    """
    results = []
    # 匹配 "D2 349" 或 "D2 (349)" 等格式
    pattern = re.compile(r"^\s*([A-Za-z]+\d{1,2})\s*(?:\(\s*)?(\d+)(?:\s*\))?\s*$")

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            raw_code = m.group(1).upper()
            code = _normalize_mard_code(raw_code)
            qty = int(m.group(2))
            is_valid = code in valid_codes
            results.append((code, qty, 1.0 if is_valid else 0.5, line))
        else:
            # 尝试宽松匹配：只要行里有色号和数字就抓
            m2 = re.search(r"([A-Za-z]\d{1,2})", line)
            m3 = re.search(r"\b(\d{3,})\b", line)  # 用量通常是3位以上
            if m2 and m3:
                code = _normalize_mard_code(m2.group(1).upper())
                is_valid = code in valid_codes
                results.append((code, int(m3.group(1)), 1.0 if is_valid else 0.5, line))

    return results


def analyze_with_vision(
    image_path: Path,
    brand: str,
    api_key: Optional[str] = None,
) -> dict:
    """
    使用 Kimi 视觉大模型分析图纸色号。

    Args:
        image_path: 图片路径
        brand: 品牌名称
        api_key: Moonshot API Key，默认从环境变量 KIMI_API_KEY 读取

    Returns:
        {"brand": str, "mode": "vision", "items": [OcrItem, ...], "raw_response": str}
    """
    key = api_key or os.environ.get("KIMI_API_KEY")
    if not key:
        raise ValueError(
            "缺少 Moonshot API Key。\n"
            "请前往 https://platform.moonshot.cn/ 注册并创建 API Key，\n"
            "然后通过以下方式之一配置：\n"
            "  1. 环境变量: set KIMI_API_KEY=sk-...\n"
            "  2. 命令行参数: --api-key sk-..."
        )

    # 尝试使用 openai 包，没有则 fallback 到 urllib
    try:
        import openai
        client = openai.OpenAI(api_key=key, base_url="https://api.moonshot.cn/v1")
        use_openai = True
    except ImportError:
        use_openai = False

    image_base64 = _image_to_base64(image_path)

    prompt = f"""你是一位拼豆图纸识别专家。请仔细识别图片中的色号清单。

图片展示的是一张拼豆（{brand}品牌）图纸的色号用量表。每个彩色方块中标注了色号和用量数字，格式通常为"色号 (用量)"，例如"D2 (349)"或"H11 (16)"。

请提取所有色号和对应的用量数字，按以下格式输出，每行一个：
色号 用量

只输出色号清单，不要任何解释、标题或额外文字。"""

    if use_openai:
        response = client.chat.completions.create(
            model="moonshot-v1-8k-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
            temperature=0.1,
        )
        raw_text = response.choices[0].message.content
    else:
        import urllib.request
        payload = json.dumps({
            "model": "moonshot-v1-8k-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]

    chart = get_chart(brand)
    valid_codes = set(chart.colors.keys()) if chart else set()
    parsed = _parse_vision_response(raw_text, valid_codes)

    # 合并重复色号（保留最大用量）
    merged: dict = {}
    for code, qty, conf, raw in parsed:
        if code not in merged:
            merged[code] = [qty, conf, raw]
        else:
            if qty and (merged[code][0] is None or qty > merged[code][0]):
                merged[code][0] = qty
            merged[code][1] = max(merged[code][1], conf)

    from .image_analyzer import OcrItem

    items = [
        OcrItem(code=code, quantity=info[0], confidence=info[1], raw_text=info[2])
        for code, info in merged.items()
    ]

    return {
        "brand": brand,
        "mode": "vision",
        "items": items,
        "raw_response": raw_text,
    }
