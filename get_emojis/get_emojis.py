import emoji

with open('input.txt', 'r', encoding='utf-8') as f:
    text = f.read()

unique_emojis = []
seen = set()

for char in text:
    if char in emoji.EMOJI_DATA and char not in seen:
        unique_emojis.append(char)
        seen.add(char)

result = ''.join(unique_emojis)

print(f"Найдено: {len(unique_emojis)}")
print(result)