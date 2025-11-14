import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://frangolandia.com/encartes/"

BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = BASE_OUTPUT / "Frangolandia"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[frangolandia.py] Pasta base de saída: {ENCARTE_DIR}")

def build_headless_chrome():
    options = webdriver.ChromeOptions()
    prefs = {
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
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

def slugify(txt: str) -> str:
    txt = re.sub(r'[\\/*?:"<>|\s]+', '_', (txt or '').strip())
    return txt[:80] or "sem_data"

def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//span[contains(@class, "elementor-button-text")]')
            )
        )
    except Exception:
        return "sem_data"
    
    for div in enc_data:
        texto = (div.text or "").strip()
        if texto:
            return slugify(texto)
    return "sem_data"

def coleta_encartes():
    driver.get(BASE_URL)
    time.sleep(3)
    encartes = driver.find_elements(By.CSS_SELECTOR, "a.jet-engine-listing-overlay-link")
    links = [e.get_attribute("href") for e in encartes if e.get_attribute("href")]
    print(f"{len(links)} link(s) de encarte encontrados na listagem.")
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
            print(f"\nAcessando: {url}")
            time.sleep(3)

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

            imagens = driver.find_elements(By.CSS_SELECTOR, "img[src*='uploads/20']")
            if not imagens:
                print(" Nenhuma imagem de encarte encontrada.")
                continue

            nome_base = slugify(url.rstrip('/').split('/')[-1] or "encarte")
            pasta_destino = ENCARTE_DIR / nome_base
            pasta_destino.mkdir(parents=True, exist_ok=True)
            print(f" Pasta do encarte: {pasta_destino}")

            for i, img in enumerate(imagens, start=1):
                src = img.get_attribute("src")
                caminho = pasta_destino / f"{nome_base}_{i}.jpg"

                baixou = False
                if src:
                    try:
                        resp = session.get(src, timeout=20)
                        if resp.status_code == 200 and resp.content:
                            with open(caminho, "wb") as f:
                                f.write(resp.content)
                            print(f" Imagem baixada: {caminho}")
                            baixou = True
                        else:
                            print(f" Download falhou ({resp.status_code}) para: {src}")
                    except Exception as req_err:
                        print(f" Erro no download de {src}: {req_err}")

                if not baixou:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                        time.sleep(0.3)
                        img.screenshot(str(caminho))
                        print(f" Screenshot salva: {caminho}")
                    except Exception as screenshot_err:
                        print(f" Falha ao salvar imagem: {screenshot_err}")

        except Exception as e:
            print(f" Erro ao processar {url}: {e}")

try:
    links = coleta_encartes()
    processar_encartes(links)
    print("\nProcesso finalizado.")
except Exception as e:
    print(f" Erro geral: {e}")
finally:
    driver.quit()
