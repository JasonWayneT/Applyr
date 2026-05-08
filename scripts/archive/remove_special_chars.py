import re

file_path = "data/workExperience.md"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace special characters with ASCII equivalents
replacements = {
    "•": "*",
    "–": "-",
    "—": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}

for src, target in replacements.items():
    content = content.replace(src, target)

# Also remove zero-width non-breaking space or other rare non-ASCII characters if any
content = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Special characters replaced in workExperience.md successfully!")
