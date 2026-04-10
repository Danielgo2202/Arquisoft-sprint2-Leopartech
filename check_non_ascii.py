import re

with open('/home/david/Documents/arquisoft/main.tf', 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f, 1):
        if not line.strip().startswith('#'):
            non_ascii = [c for c in line if ord(c) > 127]
            if non_ascii:
                print(f"Line {line_num}: {line.strip()}")
