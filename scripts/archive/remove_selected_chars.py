import re

file_path = "data/role_summaries.md"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Characters to remove: < > [ ] " { } \
chars_to_remove = ['<', '>', '[', ']', '"', '{', '}', '\\']

for ch in chars_to_remove:
    content = content.replace(ch, '')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Selected characters removed from role_summaries.md successfully!")
