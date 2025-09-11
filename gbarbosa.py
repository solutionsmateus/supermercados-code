import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://blog.gbarbosa.com.br/ofertas/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/G-Barbosa"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)

# ===== Chrome headless =====
def build_headless_chrome(download_dir: Path):
    options = webdriver.ChromeOptions()
    # Headless moderno e flags de CI
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
    # Preferências de download
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": str(download_dir),
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

driver = build_headless_chrome(ENCARTE_DIR)
wait = WebDriverWait(driver, 25)

def _list_files(dirpath: Path):
    try:
        return {p for p in dirpath.iterdir() if p.is_file()}
    except Exception:
        return set()

def _wait_new_download(dirpath: Path, before: set, timeout: int = 60):
    """
    Espera aparecer um novo arquivo na pasta (e terminar o .crdownload).
    Retorna o Path do arquivo novo ou None se não aparecer.
    """
    end = time.time() + timeout
    last_size = {}
    while time.time() < end:
        files = _list_files(dirpath)
        new_files = [f for f in files - before if not f.name.endswith(".crdownload")]
        if new_files:
            # garante que terminou (tamanho estável por 2 checagens)
            for nf in new_files:
                size1 = nf.stat().st_size
                time.sleep(1.5)
                size2 = nf.stat().st_size
                if size2 == size1:
                    return nf
        time.sleep(1)
    return None

def baixar_estado(uf: str):
    print(f"\n Baixando encartes do estado: {uf}")
    driver.get(BASE_URL)
    time.sleep(5)

    try:
        botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space()="{uf}"]')))
        botao_estado.click()
        time.sleep(5)
    except Exception as e:
        print(f"Erro ao selecionar o estado {uf}: {e}")
        return

    index = 0
    while True:
        try:
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')
            if index >= len(encartes):
                break

            print(f"\n Abrindo encarte {index+1} de {len(encartes)}...")
            # re-coleta elementos para evitar stale references
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')
            encartes[index].click()
            time.sleep(2)

            menu_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[contains(@class, "df-ui-btn") and contains(@class, "df-ui-more")]')
            ))
            menu_btn.click()
            time.sleep(1.5)

            download_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//a[contains(@class, "df-ui-download")]')
            ))

            # monitora pasta antes do clique
            before = _list_files(ENCARTE_DIR)
            download_btn.click()
            print(" Download solicitado…")

            # espera arquivo novo
            arquivo = _wait_new_download(ENCARTE_DIR, before, timeout=120)
            if arquivo:
                print(f" Download concluído: {arquivo.name}")
            else:
                print(" ⚠️ Não detectei novo arquivo na pasta (timeout).")

            # volta para lista e re-filtra o estado
            driver.get(BASE_URL)
            time.sleep(3)
            try:
                botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space()=\"{uf}\"]')))
                botao_estado.click()
                time.sleep(3)
            except Exception as e:
                print(f"Erro ao reabrir estado {uf}: {e}")
                break

            index += 1

        except Exception as e:
            print(f" Erro no encarte {index+1}: {e}")
            # tenta recuperar
            driver.get(BASE_URL)
            time.sleep(3)
            try:
                botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space()=\"{uf}\"]')))
                botao_estado.click()
                time.sleep(3)
            except:
                break
            index += 1
            continue

# Execute os estados desejados:
baixar_estado("AL")
baixar_estado("SE")

driver.quit()
print("\nFinalizado.")
