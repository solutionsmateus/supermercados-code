import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://novoatacarejo.com/oferta/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)

# === CHROME HEADLESS ===
def build_headless_chrome(download_dir: Path):
    options = webdriver.ChromeOptions()
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
    # preferências de download (mantidas)
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": str(download_dir),
        "directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

driver = build_headless_chrome(ENCARTE_DIR)
wait = WebDriverWait(driver, 20)

def encontrar_data():
    # "h6 - TEXT LOCATION OF DATES IN PAGE"
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//h6[contains(\"TEXT\")]"))
        )
    except Exception:
        return "sem_data"
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def selecionar_loja():
    driver.get(BASE_URL)
    select_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "select.select")))
    Select(select_element).select_by_visible_text("Olinda")
    time.sleep(4)  # aguarda carregar os tabloids

def clicar_nas_imagens():
    imagens = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tabloids a")))

    # abre até 2 links em novas abas
    for i in range(min(2, len(imagens))):
        link = imagens[i].get_attribute("href")
        if not link:
            continue
        driver.execute_script("window.open(arguments[0], arguments[1]);", link, "_blank")
        time.sleep(1)

    abas = driver.window_handles

    # percorre as abas recém-abertas (aba 0 é a principal)
    for i in range(1, min(3, len(abas))):
        driver.switch_to.window(abas[i])
        time.sleep(5)

        # página 1
        screenshot_path = ENCARTE_DIR / f"Ofertas_Novo_Atacarejo_{i}_pag1.png"
        driver.save_screenshot(str(screenshot_path))
        print(f" Screenshot do encarte {i} salvo em: {screenshot_path}")

        # tenta ir para a página 2 e salvar
        try:
            next_button = wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "div.pdff-ui-btn.pdff-ui-next.pdff-ui-alt.fa.fa-chevron-right[title='Next Page']"
                ))
            )
            next_button.click()
            time.sleep(5)
            screenshot_path_2 = ENCARTE_DIR / f"Ofertas_Novo_Atacarejo_{i}_pag2.png"
            driver.save_screenshot(str(screenshot_path_2))
            print(f" Screenshot do encarte {i} (pag 2) salvo em: {screenshot_path_2}")
        except Exception as e:
            print(f"Erro ao clicar/capturar a página 2 da aba {i}: {e}")

selecionar_loja()
clicar_nas_imagens()
driver.quit()
