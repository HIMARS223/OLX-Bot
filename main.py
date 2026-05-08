import asyncio
import logging
import os
from aiogram import Bot
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I am alive")
    def log_message(self, format, *args): return # Чтобы не спамить в логи

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# Запускаем в отдельном потоке
threading.Thread(target=run_health_server, daemon=True).start()
API_TOKEN = os.getenv('BOT_TOKEN')
USER_ID = os.getenv('USER_ID')

TARGET_URLS = [
    "https://www.olx.ua/uk/elektronika/igry-i-igrovye-pristavki/pristavki/q-playstation%203/?currency=UAH&search%5Bfilter_float_price%3Afrom%5D=1500&search%5Bfilter_float_price%3Ato%5D=3300&search%5Border%5D=created_at%3Adesc&search%5Bprivate_business%5D=private",
    "https://www.olx.ua/uk/elektronika/igry-i-igrovye-pristavki/pristavki/q-xbox%20360/?currency=UAH&search%5Bfilter_float_price%3Afrom%5D=1500&search%5Bfilter_float_price%3Ato%5D=2700&search%5Border%5D=created_at%3Adesc&search%5Bprivate_business%5D=private"
]

bot = Bot(token=API_TOKEN)
processed_ads = set()

def create_tiny_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=800,600") # Маленькое окно = меньше памяти на отрисовку
    options.add_argument("--proxy-server='direct://'")
    options.add_argument("--proxy-bypass-list=*")
    options.add_argument("--disable-extensions")
    
    # ЭКСТРЕМАЛЬНЫЕ НАСТРОЙКИ (отключаем всё, что можно)
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2, # Можно попробовать отключить стили
        "profile.managed_default_content_settings.cookies": 2,
        "profile.managed_default_content_settings.plugins": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
    }
    options.add_experimental_option("prefs", prefs)
    
    # Путь для Render
    options.binary_location = "/usr/bin/google-chrome"
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

async def check_olx():
    global processed_ads
    logging.info("Запуск цикла проверки...")
    
    # Создаем драйвер ОДИН РАЗ на один цикл ссылок
    driver = create_tiny_driver()
    
    try:
        for url in TARGET_URLS:
            logging.info(f"Чекаем: {url[:400]}")
            driver.get(url)
            await asyncio.sleep(5)
            
            # Ищем ссылки
            elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/d/uk/obyavlenie/"]')[:20]
            links = [el.get_attribute('href').split('?')[0] for el in elements]
            
            for link in links:
                if link not in processed_ads:
                    # Переходим в этом же окне (никаких вкладок!)
                    driver.get(link)
                    await asyncio.sleep(4)
                    
                    try:
                        price = driver.find_element(By.XPATH, "//div[@data-testid='ad-price-container']//h3").text
                        desc = driver.find_element(By.XPATH, "//div[@data-testid='ad_description']//div").text[:300]
                    except:
                        price, desc = "Не удалось вытянуть", "Нет описания"
                    
                    await bot.send_message(USER_ID, f"📦 **Новое!**\n💰 `{price}`\n🔗 {link}\n\n{desc}...", parse_mode="Markdown")
                    processed_ads.add(link)
                    
                    # Возвращаемся к списку
                    driver.back()
                    await asyncio.sleep(2)
            
            # ОЧИСТКА КЭША после каждой категории
            driver.execute_cdp_cmd('Network.clearBrowserCache', {})
            
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        driver.quit() # Убиваем браузер полностью

async def main():
    while True:
        await check_olx()
        await asyncio.sleep(800) # Раз в 10 минут (чтобы не частить)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
