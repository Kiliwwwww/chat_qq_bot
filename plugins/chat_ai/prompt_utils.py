from __future__ import annotations

import re

_FENCE_LINE = re.compile(r"^\s*```[^\s`]*\s*$")


def clean_prompt_text(text: str) -> str:
    """去掉编辑器误加的空代码块围栏，保留正文内容。

    Markdown 编辑器在 IR 模式下偶尔会把整段提示词包进 ``` 代码块，或者只留下
    一个落单的围栏，导致大模型把提示词当成代码示例，实际上不生效。这里直接
    丢掉所有只由 ``` 组成的行，让提示词始终以纯文本形式送入模型。
    """
    if not text:
        return ""
    lines = [line for line in text.replace("\r\n", "\n").split("\n") if not _FENCE_LINE.match(line)]
    return "\n".join(lines).strip()
