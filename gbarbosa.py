import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://blog.gbarbosa.com.br/ofertas/"

BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
DOWNLOAD_BASE = BASE_OUTPUT / "G-Barbosa"
DOWNLOAD_BASE.mkdir(parents=True, exist_ok=True)
print(f"[gbarbosa.py] Pasta base de saída: {DOWNLOAD_BASE}")

def build_headless_chrome(download_dir: Path):
    options = webdriver.ChromeOptions()
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
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": str(download_dir),
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

driver = build_headless_chrome(DOWNLOAD_BASE)
wait = WebDriverWait(driver, 25)

def _list_files(dirpath: Path):
    try:
        return {p for p in dirpath.iterdir() if p.is_file()}
    except Exception:
        return set()

def _wait_new_download(dirpath: Path, before: set, timeout: int = 120) -> Path | None:
    
    end = time.time() + timeout
    while time.time() < end:
        files = _list_files(dirpath)
        new_files = [f for f in files - before if not f.name.endswith(".crdownload")]
        if new_files:
            # garante término do download verificando tamanho estável
            for nf in new_files:
                s1 = nf.stat().st_size
                time.sleep(1.5)
                s2 = nf.stat().st_size
                if s1 == s2 and s2 > 0:
                    return nf
        time.sleep(1)
    return None

def _sanitize(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", s).strip()

def baixar_estado(uf: str):
    uf = uf.strip().upper()
    pasta_uf = (DOWNLOAD_BASE / uf)
    pasta_uf.mkdir(parents=True, exist_ok=True)

    print(f"\nBaixando encartes do estado: {uf}")
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
            if index >= len(encartes) or len(encartes) == 0:
                print("Não há mais encartes para este estado.")
                break

            print(f"\nAbrindo encarte {index+1} de {len(encartes)}…")
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')
            encartes[index].click()
            time.sleep(2)
            
            while True:
                try:
                    caminho_png = DOWNLOAD_BASE / f"{encartes}_{screenshot_index}.png"
                    driver.save_screenshot(str(caminho_png))
                    print(f"  Capturado: {caminho_png.name}")
                    
                    driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(1.5) 
                    new_scroll_position = driver.execute_script("return window.pageYOffset")
                    
                    if new_scroll_position == last_height:
                        print("Fim do encarte alcançado. Encerrando captura.")
                        break
                    
                    last_height = new_scroll_position
                    screenshot_index += 1
                    
                except Exception as e:
                    print(f"Não foi possível capturar as imagens ou houve um erro: {e}")
                    break 
                
                driver.get(BASE_URL)
                time.sleep(3)
                
                try:
                    botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space()="{uf}"]')))
                    botao_estado.click()
                    time.sleep(3)
                except Exception as e:
                    print(f"Erro ao reabrir estado {uf}: {e}")
                
                break

            index += 1

        except Exception as e:
            print(f"Erro no encarte {index+1}: {e}")
            driver.get(BASE_URL)
            time.sleep(3)
            try:
                botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space()="{uf}"]')))
                botao_estado.click()
                time.sleep(3)
            except:
                break
            index += 1
            continue

ESTADOS = ['AL', 'SE']

for uf in ESTADOS:
    baixar_estado(uf)

driver.quit()
print("\nFinalizado.")
