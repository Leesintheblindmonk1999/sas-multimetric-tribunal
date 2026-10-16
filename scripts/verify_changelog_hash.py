#!/usr/bin/env python3
"""verify_changelog_hash.py — Verifica que el hash inline del CHANGELOG sea autoconsistente."""
import hashlib, re

with open("CHANGELOG.md", "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")
expected = None
filtered = []
i = 0
while i < len(lines):
    line = lines[i]
    # Match "CHANGELOG.md:" followed by hash on same or next line
    m = re.match(r"^CHANGELOG\.md:\s*([a-f0-9]{64})\s*$", line)
    if m:
        expected = m.group(1)
        i += 1
        continue
    # Match "CHANGELOG.md:" with hash on next line
    if re.match(r"^CHANGELOG\.md:\s*$", line) and i + 1 < len(lines):
        m2 = re.match(r"^([a-f0-9]{64})\s*$", lines[i + 1])
        if m2:
            expected = m2.group(1)
            i += 2
            continue
    filtered.append(line)
    i += 1

if expected is None:
    print("ERROR: No se encontró línea de hash 'CHANGELOG.md: <hash>'")
    exit(1)

clean = "\n".join(filtered)
h = hashlib.sha256(clean.encode("utf-8")).hexdigest()

ok = h == expected
print(f"Hash inline: {expected}")
print(f"Hash real:   {h}")
print(f"Coincide: {ok}")
if not ok:
    print("ERROR: El hash inline NO coincide con el hash real del documento.")
    exit(1)
else:
    print("OK: Hash autoconsistente.")