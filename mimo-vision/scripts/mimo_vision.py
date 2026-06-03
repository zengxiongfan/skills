#!/usr/bin/env python3
"""mimo-vision: Image understanding via mimo-v2.5 model."""

import sys
import os
import json
import base64
import ssl
import mimetypes
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
DEFAULT_PROMPT = "请详细描述这张图片的内容"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_url(path):
    return path.startswith(('http://', 'https://'))


def is_image_file(path):
    _, ext = os.path.splitext(path.lower())
    return ext in IMAGE_EXTENSIONS


def image_to_base64_url(file_path):
    """Read local image file and return data URL with base64 encoding."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"图片文件不存在: {abs_path}")

    mime_type, _ = mimetypes.guess_type(abs_path)
    if mime_type is None:
        mime_type = 'image/png'

    with open(abs_path, 'rb') as f:
        data = f.read()

    b64 = base64.b64encode(data).decode('utf-8')
    return f"data:{mime_type};base64,{b64}"


def build_messages(image_sources, prompt):
    """Build API message payload with images and prompt."""
    content = []
    for src in image_sources:
        if is_url(src):
            image_url = src
        else:
            image_url = image_to_base64_url(src)

        content.append({
            "type": "image_url",
            "image_url": {"url": image_url}
        })

    content.append({
        "type": "text",
        "text": prompt
    })

    return [
        {
            "role": "system",
            "content": "You are MiMo, an AI assistant developed by Xiaomi with advanced image understanding capabilities. Analyze the provided image(s) carefully and respond in detail."
        },
        {
            "role": "user",
            "content": content
        }
    ]


def call_api(config, messages):
    """Call mimo-v2.5 API and return the response text."""
    payload = {
        "model": config["model"],
        "messages": messages,
        "max_completion_tokens": config.get("max_completion_tokens", 4096)
    }

    data = json.dumps(payload).encode('utf-8')
    req = Request(
        f"{config['base_url']}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "api-key": config["api_key"]
        },
        method="POST"
    )

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        with urlopen(req, timeout=120, context=ssl_ctx) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f"API请求失败 (HTTP {e.code}): {body}")
    except URLError as e:
        raise RuntimeError(f"网络连接失败: {e.reason}")


def main():
    # Force UTF-8 output on Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print("用法: mimo_vision.py <图片路径或URL> [图片路径或URL2 ...] [提问内容]")
        print("示例: mimo_vision.py /path/to/image.png '请描述这张图片'")
        sys.exit(1)

    args = sys.argv[1:]

    # Check if last argument is a prompt (not an image path/URL)
    if len(args) > 1 and not is_url(args[-1]) and not os.path.isfile(os.path.abspath(args[-1])):
        prompt = args[-1]
        image_sources = args[:-1]
    else:
        prompt = DEFAULT_PROMPT
        image_sources = args

    if not image_sources:
        print("错误: 请至少提供一个图片路径或URL", file=sys.stderr)
        sys.exit(1)

    # Validate image sources
    for src in image_sources:
        if not is_url(src):
            abs_path = os.path.abspath(src)
            if not os.path.isfile(abs_path):
                print(f"错误: 文件不存在: {abs_path}", file=sys.stderr)
                sys.exit(1)
            if not is_image_file(abs_path):
                print(f"警告: 文件可能不是支持的图片格式: {src}", file=sys.stderr)

    config = load_config()
    messages = build_messages(image_sources, prompt)
    result = call_api(config, messages)
    print(result)


if __name__ == "__main__":
    main()
