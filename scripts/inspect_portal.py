with open('app/templates/public_portal.html', 'r', encoding='utf-8') as f:
    c = f.read()

import re
titles = re.findall(r'<h3 class="text-xl font-extrabold mb-3 uppercase italic">([^<]+)</h3>', c)
print('Current 8 titles in public_portal.html:')
for idx, t in enumerate(titles):
    print(f'{idx+1}: {t}')
