import sys
with open('/home/david/Documents/arquisoft/main.tf', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('—', '-')

with open('/home/david/Documents/arquisoft/main.tf', 'w', encoding='utf-8') as f:
    f.write(content)
