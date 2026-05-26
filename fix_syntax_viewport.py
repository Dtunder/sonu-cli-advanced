with open("tools.py", "r") as f:
    text = f.read()

text = text.replace("return f\"OK: Screenshot analysiert.\\nErgebnis: {response.text}\"", "return f\"OK: Screenshot analysiert.\\\\nErgebnis: {response.text}\"")
text = text.replace("return f\"FEHLER: Benötigte Bibliothek fehlt. Führe 'pip install mss Pillow' aus.\\nDetails: {e}\"", "return f\"FEHLER: Benötigte Bibliothek fehlt. Führe 'pip install mss Pillow' aus.\\\\nDetails: {e}\"")

with open("tools.py", "w") as f:
    f.write(text)
