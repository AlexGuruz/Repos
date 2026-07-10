from pathlib import Path

p = Path(__file__).resolve().parent / "_query_arctic_disposable_inventory.py"
t = p.read_text(encoding="utf-8")
old = "(?i)arctic" + '"' + "}" * 4 + ","
new = "(?i)arctic" + '"' + "}" * 3 + ","
if old not in t:
    raise SystemExit("pattern not found")
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("ok")
