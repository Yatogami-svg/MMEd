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

def login(session):
    print(f"Попытка входа для {USERNAME}")

    # 1. Получаем страницу логина для CSRF-токена
    login_page = session.get(LOGIN_URL)
    print(f"Статус загрузки страницы логина: {login_page.status_code}")

    soup = BeautifulSoup(login_page.text, 'html.parser')

    # Ищем все поля ввода на форме
    form = soup.find('form', {'action': re.compile(r'login')})
    if not form:
        # Попробуем найти любую форму с полями login/password
        form = soup.find('form')
    if not form:
        print("Не найдена форма логина. Проверьте HTML страницы логина.")
        # Выведем первые 500 символов для отладки
        print(login_page.text[:500])
        raise Exception("Форма логина не найдена")

    # Ищем все поля input внутри формы
    inputs = form.find_all('input')
    data = {}
    for inp in inputs:
        name = inp.get('name')
        value = inp.get('value', '')
        if name:
            data[name] = value
            print(f"Найдено поле: {name} = {value[:10]}...")

    # Добавляем логин и пароль (обычно поля называются 'login' и 'password')
    # Если в форме есть поля с другими именами, нужно их переопределить
    data['login'] = USERNAME
    data['password'] = PASSWORD

    # Также добавляем remember, если есть
    if 'remember' not in data:
        data['remember'] = '1'

    # Удаляем возможный пустой _xfToken, если он есть (он уже будет из формы)
    # Отправляем POST-запрос
    action_url = form.get('action')
    if not action_url:
        action_url = LOGIN_URL
    if not action_url.startswith('http'):
        action_url = 'https://forum.adv-rp.com' + action_url

    print(f"Отправка POST на {action_url}")
    response = session.post(action_url, data=data)

    print(f"Статус ответа после логина: {response.status_code}")
    print(f"URL после логина: {response.url}")

    # Проверяем, успешен ли вход
    # Если в URL есть 'login' – скорее всего ошибка
    if 'login' in response.url and response.status_code != 200:
        raise Exception("Ошибка авторизации. Проверьте логин/пароль или токен.")

    # Также можно проверить наличие cookie с сессией
    if 'xf_session' not in session.cookies:
        print("Не найдена сессионная cookie. Возможно, вход не удался.")
        # Выведем часть ответа для отладки
        print(response.text[:500])
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
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    login(session)
    response = session.get(FORUM_URL)
    if response.status_code != 200:
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
