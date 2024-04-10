#!/usr/bin/env python3

import ast
import vscode
from pathlib import Path
import sys
import re


def handle_decorator(file_name, class_name, method_name, decorator):
    try:
        decorator_name = ".".join(
            (
                decorator.func.value.value.id,
                decorator.func.value.attr,
                decorator.func.attr,
            )
        )
    except AttributeError:
        # Probably not the decorator we're looking for
        return []

    if decorator_name != "pytest.mark.parametrize":
        return []

    print(f"Found decorator {decorator_name} in {method_name} in {class_name}")

    kwargs = decorator.keywords
    try:
        ids_kwarg = next(kwarg for kwarg in kwargs if kwarg.arg == "ids")
    except StopIteration:
        print(f"No ids parametrize kwarg found in {method_name} in {class_name}")
        return []

    chain = [obj for obj in [file_name, class_name, method_name] if obj is not None]

    decorator_results = []
    for value in ids_kwarg.value.elts:
        if isinstance(value, ast.Str):
            decorator_results.append(
                (
                    (
                        (value.lineno, value.end_lineno),
                        (value.col_offset, value.end_col_offset),
                    ),
                    "::".join(chain) + f"[{value.s}]",
                )
            )
        else:
            print(
                f"Unsupported value type {type(value)} in {method_name} in {class_name}"
            )

    return decorator_results


def handle_method(file_name, class_name, method):
    if not method.name.startswith("test_"):
        return []

    print(f"Found method {method.name} in {class_name}")

    method_results = []
    for decorator in method.decorator_list:
        if type(decorator) != ast.Call:
            continue

        method_results.extend(
            handle_decorator(file_name, class_name, method.name, decorator)
        )

    chain = [obj for obj in [file_name, class_name, method.name] if obj is not None]

    method_results.append(
        (
            (
                (method.lineno, method.end_lineno),
                (method.col_offset, method.end_col_offset),
            ),
            "::".join(chain),
        )
    )

    return method_results


def handle_class(file_name, cls):
    if not cls.name.startswith("Test"):
        return []

    print(f"Found class {cls.name}")

    class_results = []
    for child in cls.body:
        if isinstance(child, ast.FunctionDef):
            class_results.extend(handle_method(file_name, cls.name, child))

    return class_results


def does_contain(bounds, cursor):
    (ls, le), (cs, ce) = bounds
    cur_line, cur_col = cursor
    if cur_line < ls or cur_line > le:
        return False

    if cur_line == ls and cur_col < cs:
        return False

    if cur_line == le and cur_col > ce:
        return False

    return True


ext = vscode.Extension(name="testpath", display_name="Test Py", version="0.0.1")


@ext.event
def on_activate():
    return f"The Extension '{ext.name}' has started"


def edit_launch(workspace, selected):
    launch = workspace / ".vscode" / "launch.json"

    if not launch.exists():
        vscode.window.show_info_message(f"Failed to find launch.json file to insert {selected}")
        return

    with open(launch, "r") as f:
        launch_json = f.read()

    launch_json = re.sub(
        r'(\s*(?://)?\s*")tests/.+?(")', f"\\1{selected}\\2", launch_json
    )

    with open(launch, "w") as f:
        f.write(launch_json)


def get_workspace(file_name):
    root = Path("/")
    workspace = Path(file_name)
    while not (workspace / ".vscode").exists() and workspace != root:
        workspace = workspace.parent

    if workspace == root:
        vscode.window.show_info_message("Failed to find .vscode directory")
        return root

    return workspace


def parse_file(full_name, name, cursor):
    with open(full_name, "r") as f:
        text = f.read()

    tree = ast.parse(text)

    results = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            results.extend(handle_class(name, node))
        if isinstance(node, ast.FunctionDef):
            results.extend(handle_method(name, None, node))

    selected = ""
    for bounds, entry in results:
        if does_contain(bounds, cursor):
            selected = entry
            break

    return selected


@ext.command(keybind="F6")
def pytest_path():
    editor = vscode.window.ActiveTextEditor()

    if not editor:
        return

    sys.stdout.flush()

    doc = editor.document
    full_name = doc.file_name

    workspace = get_workspace(full_name)
    name = str(Path(full_name).relative_to(workspace))
    cursor = (editor.cursor.line + 1, editor.cursor.character + 1)

    selected = parse_file(full_name, name, cursor)

    if selected:
        edit_launch(workspace, selected)


vscode.build(ext)


def main():
    pass
    # parse_file(
    #     "/home/omer/repos/ocs-ci/tests/manage/mcg/test_namespace_crd.py", (522, 15)
    # )


if __name__ == "__main__":
    main()
