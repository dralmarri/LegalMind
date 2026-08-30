#!/usr/bin/env python3
import json, sys
d = json.load(open('book3_articles.json', encoding='utf-8'))
new = json.load(open(sys.argv[1], encoding='utf-8'))
for k, v in new.items():
    d['articles'][k] = v
json.dump(d, open('book3_articles.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('added:', list(new.keys()), '| total:', len(d['articles']))
