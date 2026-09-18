import os
import re
from collections import OrderedDict

def process_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tag_pattern = re.compile(r'#([A-Za-z0-9_\-]+)')

    tagged_lines = []
    for i, line in enumerate(lines):
        tags = tag_pattern.findall(line)
        if tags:
            tagged_lines.append((i, tags))

    if not tagged_lines:
        print("No tags found.")
        return

    blocks = OrderedDict()
    for idx, (line_no, tags) in enumerate(tagged_lines):
        start = line_no
        if idx + 1 < len(tagged_lines):
            end = tagged_lines[idx + 1][0]
        else:
            end = len(lines)

        # Remove tags from the block text
        block_lines = []
        for line in lines[start:end]:
            cleaned = tag_pattern.sub('', line)
            block_lines.append(cleaned)
        block_text = ''.join(block_lines)

        for tag in tags:
            blocks.setdefault(tag, []).append(block_text)

    with open(output_path, 'w', encoding='utf-8') as f:
        for tag, chunks in blocks.items():
            f.write(f"### {tag}\n\n")
            f.write(''.join(chunks).rstrip())
            f.write("\n\n")

    print(f"Wrote {output_path} ({len(blocks)} tags)")

if __name__ == "__main__":
    input_file = os.path.join(os.getcwd(), "input.txt")
    output_file = os.path.join(os.getcwd(), "output.txt")
    process_file(input_file, output_file)