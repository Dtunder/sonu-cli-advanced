import ast
import os


class RefactorPipeline:
    MAX_FUNC_LINES = 50
    MAX_COMPLEXITY = 10
    MAX_PARAMS = 7

    def detect_smells(self, path: str) -> list:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            return [f"Lesefehler: {e}"]

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return [f"SyntaxError: {e}"]

        smells = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            end_line = getattr(node, "end_lineno", None) or node.lineno
            func_lines = end_line - node.lineno
            if func_lines > self.MAX_FUNC_LINES:
                smells.append(
                    f"Zeile {node.lineno}: '{node.name}' ist {func_lines} Zeilen lang (>{self.MAX_FUNC_LINES})"
                )

            complexity = sum(
                1 for n in ast.walk(node)
                if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                  ast.With, ast.Assert, ast.BoolOp))
            )
            if complexity > self.MAX_COMPLEXITY:
                smells.append(
                    f"Zeile {node.lineno}: '{node.name}' Komplexität {complexity} (>{self.MAX_COMPLEXITY})"
                )

            args = node.args
            total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
            if total_args > self.MAX_PARAMS:
                smells.append(
                    f"Zeile {node.lineno}: '{node.name}' hat {total_args} Parameter (>{self.MAX_PARAMS})"
                )

            # Verschachtelte Funktionen
            nested = [
                n for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node
            ]
            if len(nested) > 2:
                smells.append(
                    f"Zeile {node.lineno}: '{node.name}' enthält {len(nested)} verschachtelte Funktionen"
                )

        # Duplizierte Import-Blöcke
        imports = [
            ast.dump(n) for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        if len(imports) != len(set(imports)):
            smells.append("Doppelte Imports gefunden.")

        return smells if smells else ["Keine Code-Smells gefunden."]

    def suggest_refactoring(self, path: str, client) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            return f"Lesefehler: {e}"

        smells = self.detect_smells(path)
        smell_list = "\n".join(f"- {s}" for s in smells)

        prompt = (
            f"Analysiere den Python-Code aus '{os.path.basename(path)}' und schlage konkrete Refactorings vor.\n"
            f"Gefundene Code-Smells:\n{smell_list}\n\n"
            f"Code (erste 5000 Zeichen):\n```python\n{source[:5000]}\n```\n\n"
            "Priorisierte, konkrete Refactoring-Vorschläge mit Zeilennummern. "
            "Format: Problem → Lösung → Code-Snippet falls nötig."
        )

        try:
            if client.provider == "gemini":
                resp = client.client.models.generate_content(
                    model=client.model_name,
                    contents=prompt
                )
                return resp.text
            else:
                oa = client.oa_agents.get(client.provider)
                if not oa:
                    return "Provider nicht verfügbar."
                resp = oa.client.chat.completions.create(
                    model=oa.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.choices[0].message.content
        except Exception as e:
            return f"LLM-Fehler: {e}"
