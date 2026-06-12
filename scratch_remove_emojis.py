import os
import re

# Directory containing markdown files
root_dir = "/Users/ram/Desktop/multi-agent-fraud-detection"
agents_dir = os.path.join(root_dir, "Agents")

# Find all markdown files in root_dir and agents_dir
md_files = []
for file in os.listdir(root_dir):
    if file.endswith(".md"):
        md_files.append(os.path.join(root_dir, file))

if os.path.exists(agents_dir):
    for file in os.listdir(agents_dir):
        if file.endswith(".md"):
            md_files.append(os.path.join(agents_dir, file))

# Regex for common emojis/symbols used
# Emojis range, arrows, boxes, symbols:
# 📖, 📂, 🔗, 📝, 🏛️, ⚡, 🔌, 📥, ⚖️, 🗺️, 🛠️, 📤, 🔄, ⚙️, 🚦, 💻, 🚀, 🛝
emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|\u26a1|\u2699|\u2696|\u2194|\u21aa|\u21a9|\u2714|\u274c|\u2705|\u274e|\u2934|\u2935")

for filepath in md_files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Let's clean up specific double spaces or formatting after removing emoji
    # e.g., "## 📝 Overview" -> "## Overview"
    # To do this, we search for emoji followed by optional space
    new_content = emoji_pattern.sub("", content)
    
    # Clean up double spaces in headers like "##  Overview" to "## Overview"
    new_content = re.sub(r'#\s{2,}', '# ', new_content)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Cleaned {filepath}")
