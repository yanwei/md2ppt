from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
QA_ROOT = ROOT / "qa_artifacts"
FIXTURES_DIR = QA_ROOT / "fixtures"
WORK_DIR = QA_ROOT / "workdir"
OUTPUT_HTML_DIR = QA_ROOT / "outputs" / "html"
LOG_DIR = QA_ROOT / "outputs" / "logs"
REPORT_DIR = QA_ROOT / "reports"
SCREENSHOT_DIR = QA_ROOT / "outputs" / "screenshots"


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_dirs() -> None:
    for path in (FIXTURES_DIR, WORK_DIR, OUTPUT_HTML_DIR, LOG_DIR, REPORT_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def reset_runtime_dirs() -> None:
    for path in (FIXTURES_DIR, WORK_DIR, OUTPUT_HTML_DIR, LOG_DIR):
        clean_dir(path)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for report_name in ("cli_html_test_report.md", "cli_html_test_results.json"):
        report_path = REPORT_DIR / report_name
        if report_path.exists():
            report_path.unlink()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AssertionResult:
    name: str
    passed: bool
    details: str = ""


@dataclass
class TestResult:
    test_id: str
    category: str
    description: str
    spec_reference: str
    status: str
    command: list[str]
    returncode: int
    fixture_path: str | None = None
    output_html: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    assertions: list[AssertionResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def dedent(text: str) -> str:
    return textwrap.dedent(text).strip("\n") + "\n"


def write_fixture(name: str, content: str, *, bom: bool = False) -> Path:
    path = FIXTURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if bom:
        path.write_text(content, encoding="utf-8-sig")
    else:
        path.write_text(content, encoding="utf-8")
    return path


def write_binary_fixture(name: str, data: bytes) -> Path:
    path = FIXTURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def run_cli(
    test_id: str,
    args: list[str],
    *,
    fixture_path: Path | None = None,
    output_html: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    stdout_path = LOG_DIR / f"{test_id}.stdout.txt"
    stderr_path = LOG_DIR / f"{test_id}.stderr.txt"
    command = ["uv", "run", "python", "main.py", *args]
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return proc, stdout_path, stderr_path


def read_html(path: Path | None) -> str:
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def count_slides(html: str) -> int:
    return len(re.findall(r'<div class="(?:[^"]* )?slide(?: [^"]*)?"', html))


def count_tag(html: str, tag: str) -> int:
    return len(re.findall(rf"<{tag}\b", html))


def has_regex(html: str, pattern: str) -> bool:
    return re.search(pattern, html, flags=re.DOTALL) is not None


def contains(text: str, needle: str) -> bool:
    return needle in text


def build_fixtures() -> dict[str, Path]:
    fixtures: dict[str, Path] = {}
    fixtures["simple"] = write_fixture(
        "simple.md",
        dedent(
            """
            # 第一张

            这是第一张内容。

            # 第二张

            这是第二张内容。
            """
        ),
    )
    fixtures["title"] = write_fixture(
        "my-presentation.md",
        dedent(
            """
            # 标题

            内容。
            """
        ),
    )
    fixtures["chinese"] = write_fixture(
        "中文演示.md",
        dedent(
            """
            # 中文标题

            这里有中文段落、列表和链接 [示例](https://example.com)。
            """
        ),
    )
    fixtures["empty"] = write_fixture("empty.md", "")
    fixtures["no_h1"] = write_fixture(
        "no-h1.md",
        dedent(
            """
            只有前置内容。

            ## 二级标题

            没有一级标题。
            """
        ),
    )
    fixtures["code_h1"] = write_fixture(
        "code-h1.md",
        dedent(
            """
            # 外层

            ```python
            # fake heading
            print("ok")
            ```
            """
        ),
    )
    fixtures["full"] = write_fixture(
        "full-spectrum.md",
        dedent(
            """
            前置内容会被丢弃。

            # 封面

            副标题文字，包含 **粗体**、*斜体*、~~删除线~~、==高亮==、`行内代码`。

            # 元素兼容性

            ## 列表

            - 顶层
              - 子项

            1. 第一项
            2. 第二项

            ## 任务清单

            - [ ] 未完成任务
            - [x] 已完成任务

            ## 表格

            | 列1 | 列2 |
            | --- | --- |
            | A   | B   |

            ## 数学

            行内公式：$E=mc^2$

            $$\\int_0^1 x^2 dx = \\frac{1}{3}$$

            ## Mermaid

            ```mermaid
            graph TD
                A[开始] --> B[结束]
            ```

            ## Callout

            > [!NOTE]
            > 默认标题内容

            > [!WARNING] 自定义警告
            > 警告正文

            > [!INVALID]
            > 未知类型正文

            ## 图片

            ![[nested/path/photo one.png]]

            ![图一](images/a one.png)![图二](images/b-two.png)

            ## 代码

            ```python
            def hello():
                print("hi")
            ```

            ```unknownlang
            plain text
            ```
            """
        ),
    )
    fixtures["adjacent_h1"] = write_fixture(
        "adjacent-h1.md",
        dedent(
            """
            # 第一张
            # 第二张

            第二张正文
            """
        ),
    )
    fixtures["visual"] = write_fixture(
        "visual-preview.md",
        dedent(
            """
            # HTML 显示预览

            **粗体** *斜体* ~~删除线~~ ==高亮== `行内代码`

            > [!NOTE] 说明块
            > 这是用于视觉检查的 callout。

            | 列1 | 列2 |
            | --- | --- |
            | A   | B   |

            行内公式：$E=mc^2$

            ```python
            def add(a, b):
                return a + b
            ```

            ![图一](images/a one.png)![图二](images/b-two.png)
            """
        ),
    )
    fixtures["unclosed_fence"] = write_fixture(
        "unclosed-fence.md",
        dedent(
            """
            # 代码未闭合

            ```python
            print("missing close")
            # 下一行不应触发新幻灯片
            """
        ),
    )
    fixtures["special_filename"] = write_fixture(
        "my file (1).md",
        dedent(
            """
            # Special Name

            文件名带空格和括号。
            """
        ),
    )
    fixtures["bom"] = write_fixture(
        "bom.md",
        dedent(
            """
            # BOM 标题

            带 BOM 的 Markdown。
            """
        ),
        bom=True,
    )
    png_stub = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\x0b\xe7\x02\x9d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    write_binary_fixture("images/a one.png", png_stub)
    write_binary_fixture("images/b-two.png", png_stub)
    write_binary_fixture("photo one.png", png_stub)
    return fixtures


def assertion(name: str, passed: bool, details: str = "") -> AssertionResult:
    return AssertionResult(name=name, passed=passed, details=details)


def evaluate_html_test(
    *,
    test_id: str,
    category: str,
    description: str,
    spec_reference: str,
    fixture_path: Path | None,
    output_html: Path | None,
    proc: subprocess.CompletedProcess[str],
    stdout_path: Path,
    stderr_path: Path,
    checks: list[Callable[[str], AssertionResult]],
) -> TestResult:
    html = read_html(output_html)
    assertions = [check(html) for check in checks]
    status = "passed" if proc.returncode == 0 and all(item.passed for item in assertions) else "failed"
    return TestResult(
        test_id=test_id,
        category=category,
        description=description,
        spec_reference=spec_reference,
        status=status,
        command=["uv", "run", "python", "main.py", *( [str(fixture_path)] if fixture_path else [] ), *( [str(output_html)] if output_html and fixture_path and output_html.name != fixture_path.with_suffix('.html').name else [] )],
        returncode=proc.returncode,
        fixture_path=str(fixture_path) if fixture_path else None,
        output_html=str(output_html) if output_html else None,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        assertions=assertions,
    )


def evaluate_cli_test(
    *,
    test_id: str,
    category: str,
    description: str,
    spec_reference: str,
    command: list[str],
    proc: subprocess.CompletedProcess[str],
    stdout_path: Path,
    stderr_path: Path,
    checks: list[Callable[[subprocess.CompletedProcess[str]], AssertionResult]],
    fixture_path: Path | None = None,
    output_html: Path | None = None,
) -> TestResult:
    assertions = [check(proc) for check in checks]
    status = "passed" if all(item.passed for item in assertions) else "failed"
    return TestResult(
        test_id=test_id,
        category=category,
        description=description,
        spec_reference=spec_reference,
        status=status,
        command=command,
        returncode=proc.returncode,
        fixture_path=str(fixture_path) if fixture_path else None,
        output_html=str(output_html) if output_html else None,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        assertions=assertions,
    )


def main() -> int:
    ensure_dirs()
    reset_runtime_dirs()
    fixtures = build_fixtures()
    results: list[TestResult] = []

    def out(name: str) -> Path:
        return OUTPUT_HTML_DIR / name

    # CLI-001
    output = out("simple.html")
    proc, stdout_path, stderr_path = run_cli("CLI-001", [str(fixtures["simple"]), str(output)], fixture_path=fixtures["simple"], output_html=output)
    results.append(
        evaluate_html_test(
            test_id="CLI-001",
            category="cli",
            description="基本转换",
            spec_reference="10.1 CLI-001",
            fixture_path=fixtures["simple"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("退出码为 0", proc.returncode == 0, f"returncode={proc.returncode}"),
                lambda html: assertion("生成 HTML 文件", output.exists(), str(output)),
                lambda html: assertion("包含 2 张幻灯片", count_slides(html) == 2, f"slide_count={count_slides(html)}"),
            ],
        )
    )

    # CLI-002
    output = out("custom-output.html")
    proc, stdout_path, stderr_path = run_cli("CLI-002", [str(fixtures["simple"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="CLI-002",
            category="cli",
            description="指定输出文件",
            spec_reference="10.1 CLI-002",
            fixture_path=fixtures["simple"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("退出码为 0", proc.returncode == 0, f"returncode={proc.returncode}"),
                lambda html: assertion("生成指定路径 HTML", output.exists(), str(output)),
            ],
        )
    )

    # CLI-003
    proc, stdout_path, stderr_path = run_cli("CLI-003", [str(FIXTURES_DIR / "nonexistent.md")])
    results.append(
        evaluate_cli_test(
            test_id="CLI-003",
            category="cli",
            description="文件不存在",
            spec_reference="10.1 CLI-003",
            command=["uv", "run", "python", "main.py", str(FIXTURES_DIR / "nonexistent.md")],
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda p: assertion("退出码非 0", p.returncode != 0, f"returncode={p.returncode}"),
                lambda p: assertion("输出 No such file", "no such file" in (p.stdout + p.stderr).lower(), p.stdout + p.stderr),
            ],
        )
    )

    # CLI-004
    stdout_path = LOG_DIR / "CLI-004.stdout.txt"
    stderr_path = LOG_DIR / "CLI-004.stderr.txt"
    command = ["uv", "run", "python", "main.py"]
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    results.append(
        evaluate_cli_test(
            test_id="CLI-004",
            category="cli",
            description="无参数",
            spec_reference="10.1 CLI-004",
            command=command,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda p: assertion("退出码非 0", p.returncode != 0, f"returncode={p.returncode}"),
                lambda p: assertion("输出 Usage", "Usage:" in (p.stdout + p.stderr), p.stdout + p.stderr),
            ],
        )
    )

    # CLI-005
    output = out("my-presentation.html")
    proc, stdout_path, stderr_path = run_cli("CLI-005", [str(fixtures["title"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="CLI-005",
            category="cli",
            description="标题提取",
            spec_reference="10.1 CLI-005",
            fixture_path=fixtures["title"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("HTML title 取自文件名", contains(html, "<title>my-presentation</title>")),
            ],
        )
    )

    # CLI-006
    output = out("chinese.html")
    proc, stdout_path, stderr_path = run_cli("CLI-006", [str(fixtures["chinese"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="CLI-006",
            category="cli",
            description="中文 Markdown",
            spec_reference="10.1 CLI-006",
            fixture_path=fixtures["chinese"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("退出码为 0", proc.returncode == 0, f"returncode={proc.returncode}"),
                lambda html: assertion("保留中文标题", "中文标题" in html),
                lambda html: assertion("保留中文正文", "这里有中文段落" in html),
            ],
        )
    )

    # CLI-007
    output = out("empty.html")
    proc, stdout_path, stderr_path = run_cli("CLI-007", [str(fixtures["empty"]), str(output)])
    results.append(
        evaluate_cli_test(
            test_id="CLI-007",
            category="cli",
            description="空文件生成空演示 HTML",
            spec_reference="3.3 输入文件为空 / 10.1 CLI-007",
            command=["uv", "run", "python", "main.py", str(fixtures["empty"]), str(output)],
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_path=fixtures["empty"],
            output_html=output,
            checks=[
                lambda p: assertion("应成功退出", p.returncode == 0, f"returncode={p.returncode}"),
                lambda p: assertion("应生成 HTML 文件", output.exists(), str(output)),
                lambda p: assertion("0 张幻灯片", count_slides(read_html(output)) == 0, f"slide_count={count_slides(read_html(output))}"),
            ],
        )
    )

    # CLI-BOM
    output = out("bom.html")
    proc, stdout_path, stderr_path = run_cli("CLI-BOM", [str(fixtures["bom"]), str(output)])
    results.append(
        evaluate_cli_test(
            test_id="CLI-BOM",
            category="cli",
            description="UTF-8 BOM 输入",
            spec_reference="3.3 输入文件为 UTF-8 编码，含 BOM 也支持",
            command=["uv", "run", "python", "main.py", str(fixtures["bom"]), str(output)],
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_path=fixtures["bom"],
            output_html=output,
            checks=[
                lambda p: assertion("应成功退出", p.returncode == 0, f"returncode={p.returncode}"),
                lambda p: assertion("输出包含 BOM 标题", "BOM 标题" in read_html(output), read_html(output)[:200]),
            ],
        )
    )

    # Markdown/full-spectrum
    output = out("full-spectrum.html")
    proc, stdout_path, stderr_path = run_cli("MD-FULL", [str(fixtures["full"]), str(output)])
    full_html = read_html(output)
    results.extend(
        [
            evaluate_html_test(
                test_id="MD-001",
                category="markdown",
                description="H1 分割",
                spec_reference="5.1 / 10.2 MD-001",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("包含 2 张幻灯片", count_slides(html) == 2, f"slide_count={count_slides(html)}")],
            ),
            evaluate_html_test(
                test_id="MD-003",
                category="markdown",
                description="粗体",
                spec_reference="5.2.1 / 10.2 MD-003",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 strong 标签", "<strong>粗体</strong>" in html)],
            ),
            evaluate_html_test(
                test_id="MD-004",
                category="markdown",
                description="斜体",
                spec_reference="5.2.1 / 10.2 MD-004",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 em 标签", "<em>斜体</em>" in html)],
            ),
            evaluate_html_test(
                test_id="MD-005",
                category="markdown",
                description="删除线",
                spec_reference="5.2.1 / 10.2 MD-005",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 del 标签", "<del>删除线</del>" in html)],
            ),
            evaluate_html_test(
                test_id="MD-006",
                category="markdown",
                description="高亮",
                spec_reference="5.2.1 / 10.2 MD-006",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 mark 标签", "<mark>高亮</mark>" in html)],
            ),
            evaluate_html_test(
                test_id="MD-007",
                category="markdown",
                description="行内代码",
                spec_reference="5.2.1 / 10.2 MD-007",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 code 标签", "<code>行内代码</code>" in html)],
            ),
            evaluate_html_test(
                test_id="MD-008",
                category="markdown",
                description="任务清单未完成",
                spec_reference="5.2.2 / 10.2 MD-008",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion("存在 task-list-item", 'class="task-list-item"' in html),
                    lambda html: assertion("存在未勾选 checkbox", 'type="checkbox"' in html and "checked" not in html.split("未完成任务")[0][-120:]),
                ],
            ),
            evaluate_html_test(
                test_id="MD-009",
                category="markdown",
                description="任务清单已完成",
                spec_reference="5.2.2 / 10.2 MD-009",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在已勾选 checkbox", re.search(r'type="checkbox"[^>]*checked', html) is not None)],
            ),
            evaluate_html_test(
                test_id="MD-010",
                category="markdown",
                description="表格",
                spec_reference="5.2.1 / 10.2 MD-010",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 table 结构", count_tag(html, "table") >= 1 and count_tag(html, "th") >= 2)],
            ),
            evaluate_html_test(
                test_id="MD-011",
                category="markdown",
                description="行内数学",
                spec_reference="5.2.5 / 10.2 MD-011",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 math-inline 占位节点", 'class="math-inline"' in html and 'data-math="E=mc^2"' in html)],
            ),
            evaluate_html_test(
                test_id="MD-012",
                category="markdown",
                description="块级数学",
                spec_reference="5.2.5 / 10.2 MD-012",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在 math-display 占位节点", 'class="math-display"' in html and "int_0^1" in html)],
            ),
            evaluate_html_test(
                test_id="MD-013",
                category="markdown",
                description="Mermaid 图表",
                spec_reference="5.2.4 / 10.2 MD-013",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion(
                        "存在 Mermaid 输出",
                        ('class="mermaid-rendered"' in html) or ('<div class="mermaid">' in html),
                    ),
                    lambda html: assertion(
                        "存在 Mermaid 资源或源码",
                        ('alt="diagram"' in html) or ("graph TD" in html),
                    ),
                ],
            ),
            evaluate_html_test(
                test_id="MD-014",
                category="markdown",
                description="Callout NOTE",
                spec_reference="5.2.6 / 10.2 MD-014",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion("存在 callout", 'class="callout callout-note"' in html),
                    lambda html: assertion("使用蓝色样式", "--callout-color:#3b82f6" in html and "--callout-bg:#eff6ff" in html),
                ],
            ),
            evaluate_html_test(
                test_id="MD-015",
                category="markdown",
                description="Callout WARNING",
                spec_reference="5.2.6 / 10.2 MD-015",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion("存在 warning callout", 'class="callout callout-warning"' in html),
                    lambda html: assertion("使用橙色样式", "--callout-color:#f59e0b" in html and "--callout-bg:#fffbeb" in html),
                ],
            ),
            evaluate_html_test(
                test_id="MD-016",
                category="markdown",
                description="Callout 自定义标题",
                spec_reference="5.2.6 / 10.2 MD-016",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("自定义标题出现在 callout-title", "自定义警告" in html)],
            ),
            evaluate_html_test(
                test_id="MD-018",
                category="markdown",
                description="Obsidian 图片语法",
                spec_reference="5.2.7 / 10.2 MD-018",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("路径前缀应被剥离，仅保留文件名", 'src="photo%20one.png"' in html or 'src="photo one.png"' in html, "期望仅保留 photo one.png")],
            ),
            evaluate_html_test(
                test_id="MD-019",
                category="markdown",
                description="嵌套列表",
                spec_reference="5.2.1 / 10.2 MD-019",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("存在嵌套 ul", has_regex(html, r"<ul>.*<li>顶层.*<ul>.*<li>子项</li>.*</ul>.*</li>.*</ul>"))],
            ),
            evaluate_html_test(
                test_id="MD-020",
                category="markdown",
                description="代码语法高亮",
                spec_reference="5.2.3 / 10.2 MD-020",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion("存在高亮代码块", 'class="highlight"' in html),
                    lambda html: assertion("存在 pygments token span", has_regex(html, r'<span class="[^"]+">def</span>')),
                ],
            ),
            evaluate_html_test(
                test_id="MD-020A",
                category="markdown",
                description="代码块复制按钮增强",
                spec_reference="5.2.3 / 10.2 MD-020A",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion("包含复制按钮样式", ".code-copy-btn" in html),
                    lambda html: assertion("包含代码块复制初始化脚本", "initCodeCopyButtons()" in html and "copyText(text)" in html),
                ],
            ),
            evaluate_html_test(
                test_id="MD-021",
                category="markdown",
                description="未知代码语言",
                spec_reference="5.2.3 / 10.2 MD-021",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("未知语言代码仍输出纯文本代码块", "plain text" in html and "<pre><code" in html)],
            ),
            evaluate_html_test(
                test_id="MD-022",
                category="markdown",
                description="图片并排布局",
                spec_reference="6.1.3 / 10.2 MD-022",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("CSS 包含并排图片布局规则", "p:has(img):not(:has(*:not(img)))" in html)],
            ),
            evaluate_html_test(
                test_id="NEG-IMGSPACE",
                category="boundary",
                description="图片路径含空格",
                spec_reference="9.1 图片路径含空格",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[
                    lambda html: assertion(
                        "带空格的图片应渲染为 img 标签",
                        'alt="图一"' in html and ("src=\"images/a%20one.png\"" in html or "src=\"images/a one.png\"" in html),
                        "当前 HTML 中应出现图一对应的 <img>",
                    )
                ],
            ),
            evaluate_html_test(
                test_id="MD-023",
                category="markdown",
                description="前置内容丢弃",
                spec_reference="5.1 / 10.2 MD-023",
                fixture_path=fixtures["full"],
                output_html=output,
                proc=proc,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                checks=[lambda html: assertion("前置内容不出现在 HTML", "前置内容会被丢弃" not in html)],
            ),
        ]
    )

    output = out("code-h1.html")
    proc, stdout_path, stderr_path = run_cli("MD-002", [str(fixtures["code_h1"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="MD-002",
            category="markdown",
            description="代码块内 H1 不分割",
            spec_reference="5.1 / 10.2 MD-002",
            fixture_path=fixtures["code_h1"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[lambda html: assertion("只有 1 张幻灯片", count_slides(html) == 1, f"slide_count={count_slides(html)}")],
        )
    )

    output = out("adjacent-h1.html")
    proc, stdout_path, stderr_path = run_cli("NEG-ADJ-H1", [str(fixtures["adjacent_h1"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="NEG-ADJ-H1",
            category="boundary",
            description="连续多个 H1",
            spec_reference="9.1 连续多个 H1 / H1 后紧跟另一 H1",
            fixture_path=fixtures["adjacent_h1"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("生成 2 张幻灯片", count_slides(html) == 2, f"slide_count={count_slides(html)}"),
                lambda html: assertion("第一张仅有标题也不报错", proc.returncode == 0, f"returncode={proc.returncode}"),
            ],
        )
    )

    output = out("no-h1.html")
    proc, stdout_path, stderr_path = run_cli("NEG-002", [str(fixtures["no_h1"]), str(output)])
    results.append(
        evaluate_cli_test(
            test_id="NEG-002",
            category="boundary",
            description="无 H1 的 MD",
            spec_reference="5.1 空文档或无 H1 文档 / 9.1 只有前置内容，无 H1 / 10.5 NEG-002",
            command=["uv", "run", "python", "main.py", str(fixtures["no_h1"]), str(output)],
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            fixture_path=fixtures["no_h1"],
            output_html=output,
            checks=[
                lambda p: assertion("应生成空演示而非报错", p.returncode == 0, f"returncode={p.returncode}"),
                lambda p: assertion("输出 0 张幻灯片 HTML", output.exists() and count_slides(read_html(output)) == 0, f"slide_count={count_slides(read_html(output))}"),
            ],
        )
    )

    output = out("special-filename.html")
    proc, stdout_path, stderr_path = run_cli("NEG-004", [str(fixtures["special_filename"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="NEG-004",
            category="boundary",
            description="特殊字符文件名",
            spec_reference="10.5 NEG-004",
            fixture_path=fixtures["special_filename"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("CLI 成功处理特殊文件名", proc.returncode == 0, f"returncode={proc.returncode}"),
                lambda html: assertion("title 与文件名一致", "<title>my file (1)</title>" in html),
            ],
        )
    )

    output = out("unicode-filename.html")
    proc, stdout_path, stderr_path = run_cli("NEG-005", [str(fixtures["chinese"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="NEG-005",
            category="boundary",
            description="Unicode 文件名",
            spec_reference="10.5 NEG-005",
            fixture_path=fixtures["chinese"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[lambda html: assertion("title 支持 Unicode 文件名", "<title>中文演示</title>" in html)],
        )
    )

    output = out("unclosed-fence.html")
    proc, stdout_path, stderr_path = run_cli("NEG-007", [str(fixtures["unclosed_fence"]), str(output)])
    results.append(
        evaluate_html_test(
            test_id="NEG-007",
            category="boundary",
            description="未闭合代码栅栏",
            spec_reference="9.1 未闭合的代码栅栏 / 10.5 NEG-007",
            fixture_path=fixtures["unclosed_fence"],
            output_html=output,
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("不崩溃", proc.returncode == 0, f"returncode={proc.returncode}"),
                lambda html: assertion("仅保留 1 张幻灯片", count_slides(html) == 1, f"slide_count={count_slides(html)}"),
                lambda html: assertion("代码内容被保留", "missing close" in html),
            ],
        )
    )

    results.append(
        evaluate_html_test(
            test_id="NEG-009",
            category="boundary",
            description="无效 Callout 类型",
            spec_reference="9.1 Callout 类型不存在 / 10.5 NEG-009",
            fixture_path=fixtures["full"],
            output_html=out("full-spectrum.html"),
            proc=proc,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            checks=[
                lambda html: assertion("未知 callout 使用灰色样式", "--callout-color:#64748b" in full_html or "--callout-bg:#f8fafc" in full_html, "规范要求默认灰色"),
                lambda html: assertion("未知 callout 不应带默认蓝色提示图标", "💡 Invalid" not in full_html, "规范要求无图标"),
            ],
        )
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(ROOT),
        "total": len(results),
        "passed": sum(1 for item in results if item.status == "passed"),
        "failed": sum(1 for item in results if item.status == "failed"),
        "artifacts": {
            "fixtures_dir": str(FIXTURES_DIR),
            "html_dir": str(OUTPUT_HTML_DIR),
            "log_dir": str(LOG_DIR),
            "report_dir": str(REPORT_DIR),
            "screenshot_dir": str(SCREENSHOT_DIR),
        },
        "results": [
            {
                "test_id": item.test_id,
                "category": item.category,
                "description": item.description,
                "spec_reference": item.spec_reference,
                "status": item.status,
                "command": item.command,
                "returncode": item.returncode,
                "fixture_path": item.fixture_path,
                "output_html": item.output_html,
                "stdout_path": item.stdout_path,
                "stderr_path": item.stderr_path,
                "assertions": [vars(assertion_item) for assertion_item in item.assertions],
                "notes": item.notes,
            }
            for item in results
        ],
    }
    (REPORT_DIR / "cli_html_test_results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    failed = [item for item in results if item.status == "failed"]
    failure_lines = []
    for item in failed:
        failure_lines.append(f"### {item.test_id} {item.description}")
        failure_lines.append(f"- Spec: `{item.spec_reference}`")
        failure_lines.append(f"- Command: `{' '.join(item.command)}`")
        failure_lines.append(f"- Return code: `{item.returncode}`")
        if item.fixture_path:
            failure_lines.append(f"- Fixture: `{item.fixture_path}`")
        if item.output_html:
            failure_lines.append(f"- Output HTML: `{item.output_html}`")
        for assertion_item in item.assertions:
            if not assertion_item.passed:
                failure_lines.append(f"- Failed assertion: `{assertion_item.name}`")
                if assertion_item.details:
                    failure_lines.append(f"- Details: `{assertion_item.details}`")
        failure_lines.append("")

    gap_lines = ["- No open implementation gaps detected in the current regression run."] if not failed else [
        "- Review failing assertions above; the current run no longer reports the previous BOM / Mermaid expectation mismatches.",
    ]

    report = "\n".join(
        [
            "# CLI HTML Compatibility Test Report",
            "",
            "## Scope",
            "",
            "- Source of truth: `SPEC.md` sections 5, 9, 10, plus CLI empty/BOM behaviors from section 3.3.",
            "- Excluded: Web mode, Flask API, interactive keyboard navigation.",
            "- Focus: CLI-generated HTML structure, Markdown compatibility, and display-oriented CSS/DOM hooks.",
            "",
            "## Summary",
            "",
            f"- Total tests: `{summary['total']}`",
            f"- Passed: `{summary['passed']}`",
            f"- Failed: `{summary['failed']}`",
            f"- Fixtures: `{FIXTURES_DIR}`",
            f"- HTML outputs: `{OUTPUT_HTML_DIR}`",
            f"- Logs: `{LOG_DIR}`",
            f"- Screenshots directory: `{SCREENSHOT_DIR}`",
            "",
            "## High-Signal Failures",
            "",
            *(failure_lines if failure_lines else ["- No failures."]),
            "",
            "## Likely Implementation Gaps",
            "",
            *gap_lines,
            "",
            "## Machine-Readable Report",
            "",
            f"- JSON: `{REPORT_DIR / 'cli_html_test_results.json'}`",
            "",
        ]
    )
    (REPORT_DIR / "cli_html_test_report.md").write_text(report, encoding="utf-8")

    print(json.dumps({"total": summary["total"], "passed": summary["passed"], "failed": summary["failed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
