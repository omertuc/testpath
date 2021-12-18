import ast
from rich import print
import vscode
import pdb


def handle_decorator(file_name, class_name, method_name, decorator):
    decorator_name = ".".join(
        (decorator.func.value.value.id, decorator.func.value.attr, decorator.func.attr)
    )
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


@ext.command()
def pytest_path():
    editor = vscode.window.ActiveTextEditor()
    if not editor:
        return

    doc = editor.document
    name = doc.file_name

    with open(name, "r") as f:
        text = f.read()

    tree = ast.parse(text)

    results = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            results.extend(handle_class(name, node))
        if isinstance(node, ast.FunctionDef):
            results.extend(handle_method(name, None, node))

    cursor = (editor.cursor.line + 1, editor.cursor.character + 1)

    for bounds, entry in results:
        if does_contain(bounds, cursor):
            vscode.window.show_info_message(entry)


vscode.build(ext)
