import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/Atakarejo"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)

# === CHROME HEADLESS ===
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")              # headless moderno
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")     # substitui start-maximized no headless
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
driver.get("https://atakarejo.com.br/cidade/vitoria-da-conquista")

links = driver.find_elements(By.XPATH, '//a[contains(@class, "button-download-ofertas")]')
print(f"{len(links)} encarte(s) encontrado(s).")

def encontrar_data():
    # h3 - TEXT CSS IN PAGE TO FIND THE DATE OF PAGE
    try: 
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//h3[contains("TEXT")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

for i, link in enumerate(links):
    url_pdf = link.get_attribute("href")
    if not url_pdf:
        continue
    nome = f"encarte_{i+1}.pdf"
    caminho = ENCARTE_DIR / nome
    try:
        resp = requests.get(url_pdf, timeout=20)
        if resp.status_code == 200:
            with open(caminho, "wb") as f:
                f.write(resp.content)
            print(f"Baixado: {caminho.name}")
        else:
            print(f"Falha no download ({resp.status_code}): {url_pdf}")
    except Exception as e:
        print(f"Erro ao baixar {url_pdf}: {e}")

driver.quit()
