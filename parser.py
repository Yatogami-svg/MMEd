import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os

# ------------------- НАСТРОЙКИ -------------------
FORUM_URL = "https://forum.adv-rp.com/threads/mm-distsiplinarnyi-ustav-i-ustav-sredstv-massovoi-informatsii.2619941/"
LOGIN_URL = "https://forum.adv-rp.com/login"
USERNAME = os.getenv("FORUM_USERNAME")   # из переменных окружения
PASSWORD = os.getenv("FORUM_PASSWORD")   # из переменных окружения
# ------------------------------------------------

def login(session):
    """Авторизация на форуме и получение CSRF-токена."""
    # 1. Получаем страницу логина, чтобы забрать _xfToken
    login_page = session.get(LOGIN_URL)
    soup = BeautifulSoup(login_page.text, 'html.parser')
    
    # Ищем скрытый input с name="_xfToken"
    token_input = soup.find('input', {'name': '_xfToken'})
    token = token_input.get('value') if token_input else None
    
    # 2. Отправляем POST-запрос с данными
    data = {
        'login': USERNAME,
        'password': PASSWORD,
    }
    if token:
        data['_xfToken'] = token
    
    response = session.post(LOGIN_URL, data=data)
    
    # Проверяем успешность: если в URL остался 'login' – ошибка
    if 'login' in response.url:
        raise Exception("Ошибка авторизации. Проверьте логин/пароль или токен.")
    
    print("Авторизация успешна.")
    return session

def extract_chapters(text):
    """
    Разбивает текст на главы по римским цифрам (I., II., III. и т.д.).
    Возвращает список словарей: [{'head': 'I. Общие положения', 'text': '...'}, ...]
    """
    # Паттерн для поиска заголовков глав: римская цифра + точка + пробел + текст до конца строки
    # Учитываем, что могут быть римские цифры до X (можно расширить)
    # Разбиваем по строкам
    lines = text.split('\n')
    chapters = []
    current_head = None
    current_text = []
    
    # Регулярка для римских цифр от I до X (можно расширить)
    roman_pattern = re.compile(r'^([IVX]+)\.\s*(.*)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = roman_pattern.match(line)
        if match:
            # Если уже есть текущая глава, сохраняем её
            if current_head is not None:
                chapters.append({
                    'head': current_head,
                    'text': '\n'.join(current_text).strip()
                })
            # Начинаем новую главу
            roman_num = match.group(1)
            title = match.group(2).strip()
            current_head = f"{roman_num}. {title}"
            current_text = []
        else:
            # Добавляем строку к текущей главе (если она уже начата)
            if current_head is not None:
                current_text.append(line)
            else:
                # Если глава ещё не начата, пропускаем (или можно добавить как преамбулу)
                pass
    
    # Добавляем последнюю главу
    if current_head is not None:
        chapters.append({
            'head': current_head,
            'text': '\n'.join(current_text).strip()
        })
    
    return chapters

def parse_post(post_element):
    """
    Извлекает текст из поста и разбивает на главы.
    Возвращает список глав (как для contents).
    """
    wrapper = post_element.find('div', class_='bbWrapper')
    if not wrapper:
        return []
    
    # Получаем чистый текст с сохранением структуры (заменяем <br> на \n)
    # BeautifulSoup не всегда правильно конвертирует <br>, поэтому обработаем вручную
    for br in wrapper.find_all('br'):
        br.replace_with('\n')
    
    # Извлекаем текст, удаляем лишние пробелы
    raw_text = wrapper.get_text(separator='\n')
    # Удаляем множественные переносы
    raw_text = re.sub(r'\n\s*\n', '\n', raw_text).strip()
    
    # Разбиваем на главы
    chapters = extract_chapters(raw_text)
    return chapters

def main():
    if not USERNAME or not PASSWORD:
        raise Exception("Не заданы переменные окружения FORUM_USERNAME и FORUM_PASSWORD")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # Авторизация
    login(session)
    
    # Загружаем страницу с уставами
    response = session.get(FORUM_URL)
    if response.status_code != 200:
        raise Exception(f"Не удалось загрузить страницу: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Находим все сообщения (посты) в теме
    # В HTML каждый пост – это <article class="message ..." data-author="...">
    posts = soup.find_all('article', class_='message')
    
    if len(posts) < 2:
        raise Exception("Найдено меньше 2 постов. Проверьте структуру страницы.")
    
    # Первый пост – Дисциплинарный устав, второй – Устав СМИ (по порядку)
    # Но лучше определять по содержанию: ищем ключевые слова
    sections = []
    
    for idx, post in enumerate(posts[:2]):  # берём только первые два поста
        chapters = parse_post(post)
        if not chapters:
            continue
        
        # Определяем название раздела по первому заголовку или по тексту
        # Можно просто по индексу
        if idx == 0:
            section_name = "Дисциплинарный устав СМИ"
        else:
            section_name = "Устав СМИ"
        
        sections.append({
            "name": section_name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contents": chapters
        })
    
    # Сохраняем в JSON
    output = json.dumps(sections, ensure_ascii=False, indent=2)
    with open('rules.json', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print("JSON успешно создан!")

if __name__ == "__main__":
    main()
