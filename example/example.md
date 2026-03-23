# md2ppt 演示

这是第一张幻灯片，介绍本工具的用途。

> 将 Markdown 文件转换为网页版 PPT，简洁、优雅、开箱即用。

# 核心特性

## 格式支持

- **一级标题** `#` → 对应一张幻灯片
- **二级标题** `##` / `###` → 页内小标题
- 支持代码块、表格、图片、引用等标准 Markdown 语法

## 导航方式

- 键盘左右方向键翻页
- 页面左右两侧的导航按钮
- 支持 `Home` / `End` 跳转到首尾页

# 代码示例

## Python 解析逻辑

```python
import re
import markdown

def parse_slides(md_text: str) -> list[str]:
    pattern = re.compile(r'^(?=# (?!#))', re.MULTILINE)
    parts = pattern.split(md_text)
    md = markdown.Markdown(extensions=['extra', 'fenced_code'])
    return [md.convert(p.strip()) for p in parts if p.strip().startswith('# ')]
```

## 命令行用法

```bash
# 基本用法
md2ppt slides.md

# 指定输出文件
md2ppt slides.md output.html
```

# 表格示例

## 格式对照表

| Markdown 语法 | 渲染效果 | 说明 |
|:---|:---|:---|
| `# 标题` | 幻灯片标题 | 每个 H1 对应一页 |
| `## 小标题` | 页内二级标题 | 蓝色加粗 |
| ` ```code``` ` | 代码块 | 深色背景，等宽字体 |
| `> 引用` | 引用块 | 蓝色左边框 |
| `**粗体**` | **粗体** | 加粗文字 |

## 技术栈

| 层次 | 技术 |
|:---|:---|
| 解析 | Python `markdown` 库 |
| 输出 | 纯静态 HTML + CSS + JS |
| 构建 | `uv` 包管理器 |

# 图片示例

这是一张图片。

![alt text](images\912859c62495a9b3d3bcd52be9d467ad.jpeg)
![alt text](images\dd2ff10cc4f200f16f97b83a3f876d51.jpg)
![alt text](images\55b0e79c6b430eaf05b6cbdd5031d2cd.jpg)

# 谢谢观看

本工具完全开源，欢迎贡献代码或提出建议。

**项目地址：** GitHub · md2ppt
