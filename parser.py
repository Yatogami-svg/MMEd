import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os
import time

FORUM_URL = "https://forum.adv-rp.com/threads/mm-distsiplinarnyi-ustav-i-ustav-sredstv-massovoi-informatsii.2619941/"
LOGIN_URL = "https://forum.adv-rp.com/login"
USERNAME = os.getenv("FORUM_USERNAME")
PASSWORD = os.getenv("FORUM_PASSWORD")

# Расширенный набор заголовков, имитирующий браузер Chrome
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

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
    # Добавляем заголовки для POST-запроса
    login_headers = HEADERS.copy()
    login_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    response = session.post(action_url, data=data, headers=login_headers)
    if 'login' in response.url and response.status_code != 200:
        raise Exception("Ошибка авторизации")
    if 'xf_session' not in session.cookies:
        raise Exception("Сессия не установлена")
    print("Авторизация успешна!")
    return session

def extract_chapters(text):
    lines = text.split('\n')
    chapters = []
    current_head = None
    current_text = []
    roman_pattern = re.compile(r'^([IVX]+)\.\s*(.*)$')
    for line in lines:
        line = line.strip()
        if not line:
            continue
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
    return chapters

def parse_post(post_element):
    wrapper = post_element.find('div', class_='bbWrapper')
    if not wrapper:
        return []
    for br in wrapper.find_all('br'):
        br.replace_with('\n')
    raw_text = wrapper.get_text(separator='\n')
    raw_text = re.sub(r'\n\s*\n', '\n', raw_text).strip()
    return extract_chapters(raw_text)

def main():
    if not USERNAME or not PASSWORD:
        raise Exception("Не заданы переменные окружения FORUM_USERNAME и FORUM_PASSWORD")
    session = requests.Session()
    session.headers.update(HEADERS)
    login(session)
    # После логина используем те же заголовки для GET-запроса
    response = session.get(FORUM_URL, headers=HEADERS)
    if response.status_code != 200:
        # Если 403, возможно, нужен реферар или другие заголовки
        print(f"Ошибка загрузки: {response.status_code}")
        print("Ответ сервера (первые 500 символов):")
        print(response.text[:500])
        raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
    soup = BeautifulSoup(response.text, 'html.parser')
    posts = soup.find_all('article', class_='message')
    if len(posts) < 2:
        raise Exception("Найдено меньше 2 постов")
    sections = []
    for idx, post in enumerate(posts[:2]):
        chapters = parse_post(post)
        if not chapters:
            continue
        name = "Дисциплинарный устав СМИ" if idx == 0 else "Устав СМИ"
        sections.append({
            "name": name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contents": chapters
        })
    with open('rules.json', 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    print("JSON успешно создан!")

if __name__ == "__main__":
    main()
