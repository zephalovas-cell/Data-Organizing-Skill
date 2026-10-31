"""Read-only inventory. JSON findings are NOT permission to process data."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path


def date_ok(name):
    if not re.fullmatch(r"\d{8}", name):
        return False
    try:
        dt.datetime.strptime(name, "%Y%m%d")
        return True
    except ValueError:
        return False


def audit(root, methods):
    root = Path(root).absolute()
    methods = Path(methods)
    report = {"root": str(root), "tasks": [], "issues": [],
              "processing_authorized": False,
              "limits": "仅检查目录与文件清单；描述语义、方法确认状态、原始格式和公式须另行检查。"}

    def issue(path, code, detail):
        report["issues"].append({"path": str(path), "code": code, "detail": detail})

    if not root.is_dir():
        issue(root, "NOT_DIRECTORY", "地址不是可读取的文件夹")
        return report

    def blocked_link(p):
        return p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())

    if blocked_link(root):
        issue(root, "LINK", "链接目录需确认实际范围")
        return report

    # A starting folder may be above or inside the date hierarchy.
    dated = next((p for p in [root, *root.parents] if date_ok(p.name)), None)
    initial_level = len(root.relative_to(dated).parts) if dated else None
    if initial_level is not None and initial_level >= 3:
        instrument_path = dated.joinpath(*root.relative_to(dated).parts[:2])
        try:
            known_names = [p.name for p in methods.iterdir() if p.is_dir()] if methods.is_dir() else []
            if instrument_path.name not in known_names:
                issue(instrument_path, "UNKNOWN_INSTRUMENT", "祖先仪器无完全同名通用方法")
            elif not (methods / instrument_path.name / "METHOD.md").is_file():
                issue(instrument_path, "MISSING_METHOD_DEFINITION", "方法目录缺少METHOD.md")
        except OSError as exc:
            issue(methods, "METHODS_UNREADABLE", str(exc))

    def visit(folder, level):
        try:
            children = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            issue(folder, "UNREADABLE", str(exc))
            return
        dirs, files = [], []
        for child in children:
            if blocked_link(child):
                issue(child, "LINK", "未跟随链接，需确认范围")
            elif child.is_dir():
                dirs.append(child)
            elif child.is_file():
                files.append(child)

        if level is None:
            if re.fullmatch(r"\d{6,8}", folder.name):
                issue(folder, "DATE_FORMAT", "日期目录必须是有效YYYYMMDD")
            if files:
                issue(folder, "OUTSIDE_HIERARCHY", "规范日期层级外存在文件")
        elif level == 1:
            if not re.fullmatch(r"[A-Za-z]+ - .+", folder.name):
                issue(folder, "PROJECT_NAME", "预期：英文序号 - 项目名称")
        elif level == 2:
            parts = folder.name.split("_")
            if len(parts) not in (2, 3) or not all(parts):
                issue(folder, "INSTRUMENT_NAME", "预期：仪器类型_具体型号[_测试模式]；歧义须确认")
            # Use exact string comparison, even on case-insensitive Windows.
            known = []
            if methods.is_dir():
                try:
                    known = [p.name for p in methods.iterdir() if p.is_dir()]
                except OSError as exc:
                    issue(methods, "METHODS_UNREADABLE", str(exc))
            if folder.name not in known:
                issue(folder, "UNKNOWN_INSTRUMENT", "无完全同名的通用方法；不得借用相近条目")
            elif not (methods / folder.name / "METHOD.md").is_file():
                issue(folder, "MISSING_METHOD_DEFINITION", "方法目录缺少METHOD.md")
        elif level == 3:
            instrument = folder.parent.name
            project = folder.parent.parent.name
            date = folder.parent.parent.parent.name
            match = re.fullmatch(r"([A-Za-z]+) - .+", project)
            parts = instrument.split("_")
            if match and date_ok(date) and len(parts) in (2, 3) and all(parts):
                stem = f"{date}-{match.group(1)}-{parts[0]}-{folder.name}"
                names = {p.name: p for p in files}
                description = stem + ".txt"
                output = stem + ".xlsx"
                if description not in names:
                    issue(folder, "DESCRIPTION_MISSING", f"缺少精确命名描述：{description}")
                if output in names:
                    issue(names[output], "OUTPUT_EXISTS", "询问替换或另存版本")
                raw, excluded = [], []
                for p in files:
                    generated = (p.name == description or p.name == output or
                                 p.name.startswith("~$") or
                                 (p.name.startswith(stem + "_preview") and p.suffix.lower() == ".png") or
                                 bool(re.fullmatch(re.escape(stem) + r"_v\d+\.xlsx", p.name)))
                    (excluded if generated else raw).append(p.name)
                if not raw:
                    issue(folder, "NO_RAW_CANDIDATES", "未发现原始文件候选")
                report["tasks"].append({"folder": str(folder), "instrument_key": instrument,
                                        "test_type_with_note": folder.name, "expected_stem": stem,
                                        "raw_candidates": raw, "excluded": excluded})
            else:
                issue(folder, "UNRESOLVED_IDENTITY", "祖先命名不规范，不能推定输出名称")
        elif level is not None and level > 3:
            issue(folder, "EXTRA_LEVEL", "测试类型之下存在额外目录，需确认用途")

        if level is not None and level < 3 and files:
            issue(folder, "FILES_AT_WRONG_LEVEL", "原始数据与描述应位于测试数据类型层")
        if level is not None and level < 3 and not dirs:
            issue(folder, "INCOMPLETE_HIERARCHY", "缺少后续层级")
        for child in dirs:
            child_level = (0 if date_ok(child.name) else None) if level is None else level + 1
            visit(child, child_level)

    visit(root, initial_level)
    if not report["tasks"]:
        issue(root, "NO_TASKS", "未定位到规范的数据任务文件夹")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--methods", default=str(Path(__file__).resolve().parents[1] / "methods"))
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.methods), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
