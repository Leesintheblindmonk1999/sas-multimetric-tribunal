#!/usr/bin/env python3
"""check_four_five.py — Check for residual 'four' references in paper."""
import re
with open("papers/v6/paper_v6.tex", "r", encoding="utf-8") as f:
    content = f.read()
fours = len(re.findall(r"\bfour\b", content, re.IGNORECASE))
fives = len(re.findall(r"\bfive\b", content, re.IGNORECASE))
print(f"Occurrences of 'four': {fours}")
print(f"Occurrences of 'five': {fives}")
for i, line in enumerate(content.split("\n"), 1):
    if re.search(r"\bfour\b", line, re.IGNORECASE):
        print(f"  L{i}: {line.strip()[:120]}")