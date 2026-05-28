import ast
import os
from pathlib import Path


class SemanticNavigator:
    def map_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            return f"Fehler beim Lesen von {path}: {e}"

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return f"SyntaxError in {path}: {e}"

        lines = [f"## {os.path.basename(path)}"]

        imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = [a.name for a in node.names]
                imports.append(f"{mod}.{{{', '.join(names)}}}")

        if imports:
            preview = imports[:10]
            suffix = f" ... (+{len(imports)-10})" if len(imports) > 10 else ""
            lines.append(f"**Imports:** {', '.join(preview)}{suffix}")

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                lines.append(f"\n**class {node.name}** (Zeile {node.lineno})")
                for m in methods:
                    lines.append(f"  • {m}()")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                lines.append(f"**def {node.name}**({', '.join(args)}) — Zeile {node.lineno}")

        return "\n".join(lines)

    def map_directory(self, path: str) -> str:
        results = []
        try:
            for py_file in sorted(Path(path).glob("*.py")):
                if not py_file.name.startswith("test_"):
                    results.append(self.map_file(str(py_file)))
        except Exception as e:
            return f"Fehler: {e}"
        return "\n\n---\n\n".join(results) if results else "Keine .py-Dateien gefunden."

    def find_symbol(self, symbol: str, path: str) -> list:
        matches = []
        target = Path(path)
        files = list(target.rglob("*.py")) if target.is_dir() else [target]
        for py_file in files:
            try:
                with open(py_file, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if symbol in line:
                            matches.append(f"{py_file}:{i}  {line.rstrip()}")
            except Exception:
                pass
        return matches
