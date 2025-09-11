import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://frangolandia.com/encartes/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/Frangolandia"
os.makedirs(ENCARTE_DIR, exist_ok=True)

# ========= CHROME HEADLESS =========
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    # preferências (mantive as suas para PDF; não atrapalham, mesmo não sendo usadas aqui)
    prefs = {
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)

    # headless e flags de CI
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
wait = WebDriverWait(driver, 15)

def encontrar_data():
    # Exemplo de busca por textos de botões/labels na página (ajuste o seletor se quiser usar)
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//span[contains(@class, "elementor-button-text")]')
            )
        )
    except Exception:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def coleta_encartes():
    driver.get(BASE_URL)
    time.sleep(3)
    encartes = driver.find_elements(By.CSS_SELECTOR, "a.jet-engine-listing-overlay-link")
    links = [e.get_attribute("href") for e in encartes if e.get_attribute("href")]
    return links

def processar_encartes(links):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    for url in links:
        try:
            driver.get(url)
            print(f"\n Acessando: {url}")
            time.sleep(3)

            # Clica nos itens da galeria (se houver lightbox/carrossel)
            galeria_itens = driver.find_elements(
                By.CSS_SELECTOR, "a.e-gallery-item.elementor-gallery-item.elementor-animated-content"
            )
            for item in galeria_itens:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                    time.sleep(0.2)
                    item.click()
                    time.sleep(1)
                except Exception as click_err:
                    print(f" Falha ao clicar no item da galeria: {click_err}")

            # Busca imagens (ajuste o path do ano se precisar generalizar)
            imagens = driver.find_elements(By.CSS_SELECTOR, "img[src*='uploads/2025/']")
            if not imagens:
                print(" Nenhuma imagem de encarte encontrada.")
                continue

            nome_base = url.rstrip('/').split('/')[-1] or "encarte"
            for i, img in enumerate(imagens, start=1):
                src = img.get_attribute("src")
                nome_arquivo = f"{ENCARTE_DIR}/{nome_base}_{i}.jpg"

                # Tenta baixar direto
                baixou = False
                if src:
                    try:
                        resp = session.get(src, timeout=20)
                        if resp.status_code == 200 and resp.content:
                            with open(nome_arquivo, "wb") as f:
                                f.write(resp.content)
                            print(f" Imagem baixada: {nome_arquivo}")
                            baixou = True
                        else:
                            print(f" Download falhou ({resp.status_code}) para: {src}")
                    except Exception as req_err:
                        print(f" Erro no download de {src}: {req_err}")

                # Fallback: screenshot do elemento
                if not baixou:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                        time.sleep(0.3)
                        img.screenshot(nome_arquivo)
                        print(f" Screenshot salva: {nome_arquivo}")
                    except Exception as screenshot_err:
                        print(f" Falha ao salvar imagem: {screenshot_err}")

        except Exception as e:
            print(f" Erro ao processar {url}: {e}")

try:
    links = coleta_encartes()
    processar_encartes(links)
    print("\n Processo finalizado.")
except Exception as e:
    print(f" Erro geral: {e}")
finally:
    driver.quit()
