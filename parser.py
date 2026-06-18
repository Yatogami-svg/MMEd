import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os

# ------------------- СПИСОК СТРАНИЦ ДЛЯ ПАРСИНГА -------------------
PAGES = [
    {
        "url": "https://forum.adv-rp.com/threads/mm-pravila-redaktirovaniya-ob-yavlenii-pro.2618807/",
        "type": "pro",
        "posts": [2, 3, 4, 5, 6, 7, 8, 9],
        "output": "pro.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-pravila-redaktirovaniya-ob-yavlenii-pro.2618807/",
        "type": "useful",
        "posts": [10, 11],
        "output": "useful.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-obshchiye-pravila-smi-new-gen-14-02-2025.2618334/",
        "type": "common",
        "output": "common_rules.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-o-pravila-provedeniya-efirov-pp-e.2379776/",
        "type": "ppe",
        "output": "ppe.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-o-belyi-spisok-sredstv-massovoi-informatsii.2694858/",
        "type": "white_list",
        "posts": [2],
        "output": "white_list.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-chernyi-spisok-smi-spisok-lyudei-log-izmenenii-chs-smi.2420838/",
        "type": "black_list",
        "posts": [2],
        "output": "black_list.json"
    },
    {
        "url": "https://forum.adv-rp.com/threads/mm-distsiplinarnyi-ustav-i-ustav-sredstv-massovoi-informatsii.2619941/",
        "type": "discipline",
        "output": "discipline.json"
    }
]

# ------------------- НАСТРОЙКИ ФОРУМА -------------------
LOGIN_URL = "https://forum.adv-rp.com/login"
USERNAME = os.getenv("FORUM_USERNAME")
PASSWORD = os.getenv("FORUM_PASSWORD")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0',
}

# ------------------- ФУНКЦИИ АВТОРИЗАЦИИ -------------------
def login(session):
    print(f"Попытка входа для {USERNAME}")
    login_page = session.get(LOGIN_URL, headers=HEADERS)
    soup = BeautifulSoup(login_page.text, 'html.parser')
    form = soup.find('form', {'action': re.compile(r'login')})
    if not form:
        form = soup.find('form')
    if not form:
        raise Exception("Форма логина не найдена")
    inputs = form.find_all('input')
    data = {}
    for inp in inputs:
        name = inp.get('name')
        value = inp.get('value', '')
        if name:
            data[name] = value
    data['login'] = USERNAME
    data['password'] = PASSWORD
    if 'remember' not in data:
        data['remember'] = '1'
    action_url = form.get('action')
    if not action_url:
        action_url = LOGIN_URL
    if not action_url.startswith('http'):
        action_url = 'https://forum.adv-rp.com' + action_url
    login_headers = HEADERS.copy()
    login_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    response = session.post(action_url, data=data, headers=login_headers)
    if 'login' in response.url and response.status_code != 200:
        raise Exception("Ошибка авторизации")
    if 'xf_session' not in session.cookies:
        raise Exception("Сессия не установлена")
    print("Авторизация успешна!")
    return session

# ------------------- ОБЩИЕ ФУНКЦИИ ПАРСИНГА -------------------
def extract_chapters(raw_text):
    raw_text = re.sub(r'[\u200b\u200c\u200d\u2028\u2029]', '', raw_text)
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.fullmatch(r'[IVX]+', line) and i+1 < len(lines):
            next_line = lines[i+1]
            if next_line.startswith('.'):
                merged.append(line + next_line)
                i += 2
                continue
        merged.append(line)
        i += 1
    chapters = []
    current_head = None
    current_text = []
    roman_pattern = re.compile(r'^([IVX]+)\.\s*(.*)$')
    for line in merged:
        match = roman_pattern.match(line)
        if match:
            if current_head is not None:
                chapters.append({'head': current_head, 'text': '\n'.join(current_text).strip()})
            roman_num = match.group(1)
            title = match.group(2).strip()
            current_head = f"{roman_num}. {title}"
            current_text = []
        else:
            if current_head is not None:
                current_text.append(line)
    if current_head is not None:
        chapters.append({'head': current_head, 'text': '\n'.join(current_text).strip()})
    return [ch for ch in chapters if ch['text'] or ch['head']]

def get_post_text(post_element):
    wrapper = post_element.find('div', class_='bbWrapper')
    if not wrapper:
        wrapper = post_element.find('article', class_='message-body')
    if not wrapper:
        wrapper = post_element.find('div', class_='message-body')
    if not wrapper:
        wrapper = post_element.find('div', class_='message-content')
    if not wrapper:
        wrapper = post_element.find('div', class_=re.compile(r'message-content'))
    if not wrapper:
        wrapper = post_element.find('div', class_='message-main')
    if not wrapper:
        return ""
    for br in wrapper.find_all('br'):
        br.replace_with('\n')
    text = wrapper.get_text(separator='\n')
    text = re.sub(r'\n\s*\n', '\n', text).strip()
    text = re.sub(r'[\u200b\u200c\u200d]', '', text)
    return text

def get_post_chapters(post_element):
    text = get_post_text(post_element)
    return extract_chapters(text)

def post_as_one_chapter(post_element, default_head=""):
    text = get_post_text(post_element)
    if not text:
        return None
    lines = text.split('\n')
    head = lines[0] if lines else default_head
    body = '\n'.join(lines[1:]).strip()
    return {'head': head, 'text': body}

# ------------------- ПАРСЕРЫ ДЛЯ РАЗНЫХ ТИПОВ СТРАНИЦ -------------------
def parse_pro(posts):
    sections = []
    for idx, post in enumerate(posts, start=2):
        text = get_post_text(post)
        if not text:
            continue
        lines = text.split('\n')
        head = lines[0] if lines else f"Раздел {idx}"
        sections.append({'head': head, 'text': '\n'.join(lines[1:]).strip()})
    return [{
        "name": "Правила редактирования объявлений (ПРО)",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": sections
    }]

def parse_useful(posts):
    sections = []
    for idx, post in enumerate(posts, start=10):
        text = get_post_text(post)
        if not text:
            continue
        lines = text.split('\n')
        head = lines[0] if lines else f"Полезное ч.{idx-9}"
        sections.append({'head': head, 'text': '\n'.join(lines[1:]).strip()})
    return [{
        "name": "Полезное",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": sections
    }]

def parse_common(posts):
    sections = []
    for idx, post in enumerate(posts, start=1):
        chapter = post_as_one_chapter(post, default_head=f"Раздел {idx}")
        if chapter:
            sections.append(chapter)
    return [{
        "name": "Общие правила СМИ",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": sections
    }]

def parse_ppe(posts):
    sections = []
    for idx, post in enumerate(posts, start=1):
        chapter = post_as_one_chapter(post, default_head=f"Раздел {idx}")
        if chapter:
            sections.append(chapter)
    return [{
        "name": "Правила проведения эфиров (ППЭ)",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": sections
    }]

def parse_white_list(posts):
    if not posts:
        return []
    post = posts[0]
    text = get_post_text(post)
    match = re.search(r'РЕЕСТР БЕЛОГО СПИСКА\s*(.*)', text, re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1).strip()
    lines = text.split('\n')
    items = [line.strip() for line in lines if line.strip()]
    return [{
        "name": "Белый список СМИ",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": [{"head": "Реестр", "text": '\n'.join(items)}]
    }]

def parse_black_list(posts):
    if not posts:
        return []
    post = posts[0]
    wrapper = post.find('div', class_='bbWrapper')
    if not wrapper:
        return []
    tables = wrapper.find_all('table')
    if tables:
        data = []
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if cells:
                    nick = cells[0].get_text(strip=True)
                    reason = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    data.append({'nick': nick, 'reason': reason, 'date': date})
        text_lines = []
        for item in data:
            text_lines.append(f"{item['nick']} — {item['reason']} ({item['date']})")
        text = '\n'.join(text_lines)
    else:
        text = get_post_text(post)
    return [{
        "name": "Чёрный список СМИ",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "contents": [{"head": "Список", "text": text}]
    }]

def parse_discipline(posts):
    """Дисциплинарный устав и устав СМИ (2 поста)"""
    sections = []
    if len(posts) < 2:
        return []
    for idx, post in enumerate(posts[:2]):
        chapters = get_post_chapters(post)
        if not chapters:
            continue
        name = "Дисциплинарный устав СМИ" if idx == 0 else "Устав СМИ"
        sections.append({
            "name": name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contents": chapters
        })
    return sections

# ------------------- ОСНОВНАЯ ФУНКЦИЯ -------------------
def main():
    if not USERNAME or not PASSWORD:
        raise Exception("Не заданы переменные окружения FORUM_USERNAME и FORUM_PASSWORD")

    session = requests.Session()
    session.headers.update(HEADERS)
    login(session)

    headers_get = HEADERS.copy()
    headers_get['Referer'] = 'https://forum.adv-rp.com/'

    for page in PAGES:
        print(f"\nОбработка: {page['url']} (тип: {page['type']})")
        response = session.get(page['url'], headers=headers_get)
        if response.status_code != 200:
            print(f"  Ошибка загрузки: {response.status_code}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        all_posts = soup.find_all('article', class_='message')
        print(f"  Найдено постов: {len(all_posts)}")

        if "posts" in page:
            posts = []
            for num in page["posts"]:
                if num <= len(all_posts):
                    posts.append(all_posts[num-1])
                else:
                    print(f"  Пост #{num} не найден (всего {len(all_posts)})")
        else:
            posts = all_posts

        if not posts:
            print("  Нет постов для парсинга")
            continue

        parser = {
            "pro": parse_pro,
            "useful": parse_useful,
            "common": parse_common,
            "ppe": parse_ppe,
            "white_list": parse_white_list,
            "black_list": parse_black_list,
            "discipline": parse_discipline
        }.get(page["type"])
        if not parser:
            print(f"  Неизвестный тип: {page['type']}")
            continue

        result = parser(posts)
        if not result:
            print("  Результат пустой")
            continue

        output_file = page.get("output", f"{page['type']}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  Сохранён {output_file}")

    # ------------------- ОБЪЕДИНЕНИЕ ВСЕХ РАЗДЕЛОВ В ОДИН JSON -------------------
    print("\nОбъединение всех разделов в rules.json...")
    all_sections = []
    files_to_merge = [
        'pro.json',
        'useful.json',
        'common_rules.json',
        'ppe.json',
        'white_list.json',
        'black_list.json',
        'discipline.json'
    ]
    for fname in files_to_merge:
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_sections.extend(data)
                elif isinstance(data, dict):
                    all_sections.append(data)
                else:
                    print(f"  Неизвестный формат в {fname}, пропуск")
    if all_sections:
        with open('rules.json', 'w', encoding='utf-8') as f:
            json.dump(all_sections, f, ensure_ascii=False, indent=2)
        print(f"  Создан rules.json с {len(all_sections)} разделами")
    else:
        print("  Не удалось создать rules.json – нет данных")

    print("\nВсе страницы обработаны!")

if __name__ == "__main__":
    main()
