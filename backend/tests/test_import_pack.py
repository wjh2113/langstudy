"""Markdown topic import. Run: python tests/test_import_pack.py"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GATEWAY_API_KEY", "")
os.environ.setdefault("LLM_API_KEY", "")

from app.import_pack import PROMPT, parse_documents, read_upload  # noqa: E402

SAMPLE = """
# 餐厅点餐

语言: en
级别: intermediate
形式: questions

## 场景

你坐在餐厅里看菜单。

## 标题

Ordering Dinner

## 问题

### What kind of dishes usually catch your eye first, and why?
提示: 可以说口味或价格。

### Describe one dish you might order tonight.
提示: 说说名字和味道。

## 单词

### menu
读音: /ˈmenjuː/
词性: 名词
释义: 菜单
例句: Could I see the menu? | 我能看一下菜单吗？

## 语法

### would like
讲解: 用 would like 礼貌地说想要什么。
易错: 后面直接加名词。
例句: I would like the soup. | 我想要汤。

## 句型

### Could I have + 名词
用法: 点餐时礼貌地要一样东西。
例句: Could I have a salad? | 我能要一份沙拉吗？

# 缺格式

这里没有语言和形式。
"""

DIALOGUE = """
# 点餐对话

语言: 英语
级别: 中级
形式: 情景对话

## 场景

你在咖啡店点单。

## 角色

### A
名字: Alex
说明: 顾客

### B
名字: Mia
说明: 服务员

## 台词

### A
Hi, can we get a table for two, please?

### B
Sure, right this way.
"""


def test_questions_and_notes():
    ready, errors = parse_documents([SAMPLE])
    assert len(ready) == 1 and errors and "缺格式" in errors[0]
    content, notes = ready[0]["content"], ready[0]["notes"]
    assert content["mode"] == "questions" and content["language"] == "en"
    assert content["topic"] == "餐厅点餐" and len(content["questions"]) == 2
    assert content["questions"][0]["tip"].startswith("可以说")
    assert notes["vocabulary"][0]["word"] == "menu"
    assert notes["vocabulary"][0]["exampleTranslation"] == "我能看一下菜单吗？"
    assert notes["grammar"][0]["point"] == "would like"
    assert notes["patterns"][0]["examples"][0]["text"] == "Could I have a salad?"


def test_dialogue_aliases_and_zip():
    ready, errors = parse_documents([DIALOGUE])
    assert not errors
    content = ready[0]["content"]
    assert content["language"] == "en" and content["mode"] == "dialogue"
    assert [line["role"] for line in content["lines"]] == ["A", "B"]
    assert content["roles"][0]["name"] == "Alex"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("topics/order.md", DIALOGUE)
        zf.writestr("__MACOSX/order.md", "skip")
    texts = read_upload("pack.zip", buf.getvalue())
    assert len(texts) == 1 and "点餐对话" in texts[0]


def test_prompt_follows_the_courseware():
    assert "有课件时，以课件为主" in PROMPT
    assert "没有课件时" in PROMPT
    assert "两种都要" in PROMPT
    assert "每个级别都要生成" in PROMPT
    assert "写多了也会全部导入" in PROMPT
    assert "会一起导入" in PROMPT
    assert "不要为了凑数去编" in PROMPT
    assert "不要用代码块把全文包起来" in PROMPT


def test_notes_keep_every_item():
    grammar = "\n".join(f"### 语法{i}\n讲解: 讲解{i}\n例句: Example {i}. | 翻译{i}" for i in range(12))
    patterns = "\n".join(f"### 句型{i}\n用法: 用法{i}\n例句: Pattern {i}. | 译文{i}" for i in range(25))
    text = f"""# 点餐

语言: en
级别: advanced
形式: questions

## 场景

在餐厅点餐。

## 问题

### What would you like?
提示: 说菜名。

## 语法

{grammar}

## 句型

{patterns}
"""
    ready, errors = parse_documents([text])
    assert not errors
    notes = ready[0]["notes"]
    assert len(notes["grammar"]) == 12
    assert len(notes["patterns"]) == 25


def test_levels_and_modes_import_together():
    text = """# 餐厅点餐

语言: en
级别: beginner
形式: questions

## 场景

在餐厅。

## 问题

### What would you like?
提示: 说菜名。

# 餐厅点餐

语言: en
级别: intermediate
形式: dialogue

## 场景

在餐厅点餐。

## 角色

### A
名字: Alex
说明: 服务员

### B
名字: Mia
说明: 客人

## 台词

### A
Hello, can I help you?

### B
A table for two, please.
"""
    ready, errors = parse_documents([text])
    assert not errors
    assert len(ready) == 2
    assert ready[0]["content"]["level"] == "beginner" and ready[0]["content"]["mode"] == "questions"
    assert ready[1]["content"]["level"] == "intermediate" and ready[1]["content"]["mode"] == "dialogue"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
