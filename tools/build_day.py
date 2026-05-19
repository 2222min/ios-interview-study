#!/usr/bin/env python3
"""Convert dayNN.md content to HTML data block, replace in HTML file.
Usage: python3 build_day.py <day_number>
"""
import re, os, sys

if len(sys.argv) != 2:
    print("Usage: python3 build_day.py <day_number>")
    sys.exit(1)

DAY = int(sys.argv[1])

md_path = f"/Users/finda0603/Desktop/ios-interview-study/days/day{DAY:02d}.md"
html_path = "/Users/finda0603/Desktop/AIDLC/ios-bigtech-interview-20-day-plan-deep.html"

with open(md_path, 'r', encoding='utf-8') as f:
    md = f.read()

# 1. Title
title_match = re.match(r'^# Day \d+ — (.+)', md)
title = title_match.group(1).strip() if title_match else f"Day {DAY}"

# 2. Tags
tags_match = re.search(r'\*\*태그\*\*:\s*(.+)', md)
tags = []
if tags_match:
    tags = [t.strip() for t in tags_match.group(1).split('·')]

# 3. Topics — split by "## N." in 핵심 정리 section
core_match = re.search(r'## 📝 핵심 정리\n(.*?)(?=## 💬 꼬리 질문)', md, re.DOTALL)
core_content = core_match.group(1) if core_match else ""

topic_pattern = re.compile(r'\n## (\d+)\.\s+(.+?)\n(.*?)(?=\n## \d+\.|\Z)', re.DOTALL)
topics = []
for m in topic_pattern.finditer(core_content):
    topics.append({'num': m.group(1), 'name': m.group(2).strip(), 'content': m.group(3).strip()})

# 4. Questions — supports both "꼬리 질문 & 면접 답변" and "꼬리 질문 (면접 답변)"
q_section = re.search(r'## 💬 꼬리 질문[^\n]*\n(.*?)(?=\n## ✏️ 퀴즈)', md, re.DOTALL)
questions = []
if q_section:
    q_content = q_section.group(1)
    q_pattern = re.compile(r'### Q(\d+)\.\s+(.+?)\n+(.*?)(?=\n### Q\d+\.|\n---\n*$|\Z)', re.DOTALL)
    for m in q_pattern.finditer(q_content):
        qtext = m.group(2).strip()
        # Strip trailing badge like `[기본 / 빈출]`
        qtext = re.sub(r'\s*`\[[^\]]+\]`\s*$', '', qtext).strip()
        qanswer = re.sub(r'\n---\s*$', '', m.group(3).strip()).strip()
        questions.append({'num': m.group(1), 'q': qtext, 'answer': qanswer})

# 5. Quizzes
quiz_section = re.search(r'## ✏️ 퀴즈\n(.*?)(?=\n## 🧩|\Z)', md, re.DOTALL)
quizzes = []
if quiz_section:
    qz_content = quiz_section.group(1)
    qz_pattern = re.compile(r'### 문제 (\d+)\n+(.*?)\n+\*\*정답[:：]?\s*([A-D])\*\*', re.DOTALL)
    for m in qz_pattern.finditer(qz_content):
        qzbody = m.group(2).strip()
        # Find first option (A.) — supports both "- A." and "✅ **A.**" formats
        a_match = re.search(r'(?:✅\s*\*\*A\.\*\*|\-\s+A\.)', qzbody)
        if not a_match:
            continue
        opts_start = a_match.start()
        qztext = qzbody[:opts_start].strip()
        opts_block = qzbody[opts_start:]
        opts = []
        for line in opts_block.split('\n'):
            line = line.strip()
            # Match "- A. opt" or "✅ **A.** opt" or "**A.** opt"
            mopt = re.match(r'(?:✅\s*)?(?:\-\s+|\*\*)?([A-D])\.?\*?\*?\s+(.+)', line)
            if mopt:
                opt_text = mopt.group(2).strip()
                # Strip trailing markdown
                opt_text = re.sub(r'\s+$', '', opt_text)
                opts.append(opt_text)
        # Take only first 4 options
        opts = opts[:4]
        ans_idx = ord(m.group(3)) - ord('A')
        # Find hint
        hint = '핵심 정리를 다시 확인해보세요.'
        # Look for hint after this 정답 line
        rest = qz_content[m.end():]
        next_problem = rest.find('### 문제')
        if next_problem < 0:
            next_problem = len(rest)
        scope = rest[:next_problem]
        hint_match = re.search(r'💡\s*\*\*힌트\*\*[:：]?\s*(.+)', scope)
        if hint_match:
            hint = hint_match.group(1).strip()
        quizzes.append({'num': m.group(1), 'q': qztext, 'opts': opts, 'answer': ans_idx, 'hint': hint})

print(f"Day {DAY} — Topics: {len(topics)}, Questions: {len(questions)}, Quizzes: {len(quizzes)}")

# === MD → HTML ===

def md_to_html(md_text):
    s = md_text
    
    def replace_code(m):
        code = m.group(1).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return '<pre>' + code + '</pre>'
    s = re.sub(r'```(?:\w*)\n(.*?)\n```', replace_code, s, flags=re.DOTALL)
    
    def convert_table(m):
        lines = m.group(0).strip().split('\n')
        if len(lines) < 2:
            return m.group(0)
        header_cells = [c.strip() for c in lines[0].strip('|').split('|')]
        rows = []
        for line in lines[2:]:
            if not line.strip().startswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            rows.append(cells)
        result = '<table style="width:100%;font-size:13px;border-collapse:collapse;margin:10px 0">'
        result += '<tr style="background:var(--g1)">'
        for h in header_cells:
            result += f'<th style="padding:10px;text-align:left">{h}</th>'
        result += '</tr>'
        for row in rows:
            result += '<tr>'
            for cell in row:
                cell = re.sub(r'`([^`]+)`', r'<code>\1</code>', cell)
                cell = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', cell)
                result += f'<td style="padding:10px;border-top:1px solid var(--g2)">{cell}</td>'
            result += '</tr>'
        result += '</table>'
        return result
    s = re.sub(r'(?:^\|.*\|$\n)+', convert_table, s, flags=re.MULTILINE)
    
    def convert_blockquote(m):
        text = m.group(0)
        lines = [re.sub(r'^>\s?', '', l) for l in text.split('\n')]
        body = '\n'.join(lines).strip()
        body = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', body)
        body = re.sub(r'`([^`]+)`', r'<code>\1</code>', body)
        return f'<div class="highlight">{body}</div>'
    s = re.sub(r'(?:^>.*\n?)+', convert_blockquote, s, flags=re.MULTILINE)
    
    s = re.sub(r'^####\s+(.+)$', r'<h5>\1</h5>', s, flags=re.MULTILINE)
    s = re.sub(r'^###\s+(.+)$', r'<h5>\1</h5>', s, flags=re.MULTILINE)
    s = re.sub(r'^##\s+(.+)$', r'<h5>\1</h5>', s, flags=re.MULTILINE)
    
    def convert_ul(m):
        block = m.group(0)
        items = []
        for line in block.split('\n'):
            line = line.strip()
            mli = re.match(r'-\s+(.+)', line)
            if mli:
                items.append(f'<li>{mli.group(1)}</li>')
        return '<ul>' + ''.join(items) + '</ul>'
    s = re.sub(r'(?:^-\s+.+\n?)+', convert_ul, s, flags=re.MULTILINE)
    
    def convert_ol(m):
        block = m.group(0)
        items = []
        for line in block.split('\n'):
            line = line.strip()
            mli = re.match(r'\d+\.\s+(.+)', line)
            if mli:
                items.append(f'<li>{mli.group(1)}</li>')
        return '<ol>' + ''.join(items) + '</ol>'
    s = re.sub(r'(?:^\d+\.\s+.+\n?)+', convert_ol, s, flags=re.MULTILINE)
    
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', s)
    
    paragraphs = []
    for block in s.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block.startswith('<') or block.startswith('---'):
            paragraphs.append(block)
        else:
            paragraphs.append(f'<p>{block}</p>')
    s = '\n'.join(paragraphs)
    s = re.sub(r'<p>---</p>', '', s)
    s = re.sub(r'^---+$', '', s, flags=re.MULTILINE)
    return s

icons_cycle = ['blue', 'green', 'purple', 'orange']

js_topics = []
for i, t in enumerate(topics):
    icon = icons_cycle[i % len(icons_cycle)]
    detail_html = md_to_html(t['content'])
    detail_html = detail_html.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    name_escaped = (t['name']).replace('\\', '\\\\').replace('"', '\\"')
    js_topics.append('{name:"' + name_escaped + '",icon:"' + icon + '",\ndetail:`\n' + detail_html + '\n`}')

js_questions = []
for q in questions:
    qtext = q['q'].replace('\\', '\\\\').replace('"', '\\"')
    answer_html = md_to_html(q['answer'])
    answer_html = answer_html.replace('\\', '\\\\').replace('"', '\\"')
    qnum_int = int(q['num'])
    level = 'advanced' if qnum_int >= 8 else 'basic'
    freq = 'true' if qnum_int <= 12 else 'false'
    js_questions.append('{q:"' + qtext + '",level:"' + level + '",freq:' + freq + ',\nanswer:"' + answer_html + '"}')

js_quizzes = []
for qz in quizzes:
    qtext = qz['q'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '<br>')
    opts_arr = ','.join(['"' + o.replace('\\', '\\\\').replace('"', '\\"') + '"' for o in qz['opts']])
    hint = qz.get('hint', '핵심 정리를 다시 확인해보세요.').replace('\\', '\\\\').replace('"', '\\"')
    js_quizzes.append('{q:"' + qtext + '",\nopts:[' + opts_arr + '],answer:' + str(qz['answer']) + ',hint:"' + hint + '"}')

day_js = '{day:' + str(DAY) + ',title:"' + title.replace('"', '\\"') + '",\n'
day_js += 'tags:[' + ','.join(['"' + t.replace('"', '\\"') + '"' for t in tags]) + '],\n'
day_js += 'topics:[\n' + ',\n'.join(js_topics) + '\n],\n'
day_js += 'questions:[\n' + ',\n'.join(js_questions) + '\n],\n'
day_js += 'quizzes:[\n' + ',\n'.join(js_quizzes) + '\n]\n}'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

day_start = html.find('{day:' + str(DAY) + ',title:')
next_day_start = html.find('{day:' + str(DAY+1) + ',title:')

if day_start < 0:
    print(f"ERROR: Cannot find Day {DAY} marker")
    sys.exit(1)

if next_day_start > 0:
    # Replace from day_start to just before next day (keep ",\n" boundary)
    m = re.search(r',\s*\n\s*\{day:' + str(DAY+1) + ',', html[day_start:])
    if not m:
        print(f"ERROR: cannot find Day {DAY+1} boundary")
        sys.exit(1)
    abs_end = day_start + m.start()
else:
    # Last day — find closing ];
    m = re.search(r'\n\];\nvar cur', html[day_start:])
    if not m:
        print(f"ERROR: cannot find end marker")
        sys.exit(1)
    abs_end = day_start + m.start()

new_html = html[:day_start] + day_js + html[abs_end:]

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"Done! HTML size: {os.path.getsize(html_path)} bytes")
print(f"Day {DAY} JS size: {len(day_js)} bytes")
