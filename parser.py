import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os

FORUM_URL = "https://forum.adv-rp.com/threads/mm-distsiplinarnyi-ustav-i-ustav-sredstv-massovoi-informatsii.2619941/"
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

def extract_chapters(text):
    # Удаляем невидимые символы и исправляем заголовки глав
    text = re.sub(r'[\u200b\u200c\u200d]', '', text)
    # Объединяем разорванные заголовки: I\n. Общие положения. -> I. Общие положения.
    text = re.sub(r'(I|II|III|IV|V|VI|VII|VIII|IX|X)\s*\n\s*\.\s*', r'\1. ', text)
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
        print("Не найден контейнер с содержимым поста")
        return []
    
    for br in wrapper.find_all('br'):
        br.replace_with('\n')
    raw_text = wrapper.get_text(separator='\n')
    raw_text = re.sub(r'\n\s*\n', '\n', raw_text).strip()
    
    # Предобработка
    raw_text = re.sub(r'[\u200b\u200c\u200d]', '', raw_text)
    raw_text = re.sub(r'(I|II|III|IV|V|VI|VII|VIII|IX|X)\s*\n\s*\.\s*', r'\1. ', raw_text)
    
    print(f"Извлечённый текст (первые 500 символов после предобработки):")
    print(raw_text[:500] if raw_text else "Текст пуст")
    return extract_chapters(raw_text)

def main():
    if not USERNAME or not PASSWORD:
        raise Exception("Не заданы переменные окружения FORUM_USERNAME и FORUM_PASSWORD")
    session = requests.Session()
    session.headers.update(HEADERS)
    login(session)

    headers_get = HEADERS.copy()
    headers_get['Referer'] = 'https://forum.adv-rp.com/'
    response = session.get(FORUM_URL, headers=headers_get)
    if response.status_code != 200:
        print(f"Ошибка загрузки: {response.status_code}")
        print(response.text[:1000])
        raise Exception(f"Не удалось загрузить страницу: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    posts = soup.find_all('article', class_='message')
    print(f"Найдено постов: {len(posts)}")

    if len(posts) == 0:
        posts = soup.find_all('div', class_=re.compile(r'.*message.*'))
        print(f"Найдено div с message: {len(posts)}")

    if len(posts) < 2:
        print("Не найдено достаточно постов. Вывод первых 2000 символов HTML:")
        print(response.text[:2000])
        posts = soup.find_all('article')
        print(f"Всего article: {len(posts)}")

    sections = []
    for idx, post in enumerate(posts[:2]):
        chapters = parse_post(post)
        if not chapters:
            print(f"Пост {idx} не содержит глав")
            continue
        name = "Дисциплинарный устав СМИ" if idx == 0 else "Устав СМИ"
        sections.append({
            "name": name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contents": chapters
        })
        print(f"Пост {idx}: найдено {len(chapters)} глав")

    with open('rules.json', 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    print("JSON успешно создан!")

if __name__ == "__main__":
    main()
