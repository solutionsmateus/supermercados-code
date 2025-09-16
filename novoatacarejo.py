import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://novoatacarejo.com/oferta/"
CIDADE = "Olinda"  # ajuste se necessário

# === SAÍDA PADRONIZADA (usa env OUTPUT_DIR; fallback ./Encartes/Novo-Atacarejo) ===
BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
OUT_BASE = BASE_OUTPUT / "Novo-Atacarejo"
OUT_BASE.mkdir(parents=True, exist_ok=True)
print(f"[novoatacarejo.py] Pasta base de saída: {OUT_BASE}")

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
    # preferências de download (se algum PDF for baixado)
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": str(download_dir),
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

driver = build_headless_chrome(OUT_BASE)
wait = WebDriverWait(driver, 25)

def slugify(txt: str) -> str:
    txt = re.sub(r'[\\/*?:"<>|\s]+', '_', (txt or '').strip())
    return txt[:80] or "sem_data"

def detectar_validade() -> str:
    """
    Tenta capturar uma indicação de validade/período exibida na página.
    Ajuste dos seletores pode ser necessário se o site mudar.
    """
    candidatos = [
        (By.XPATH, "//h6[contains(translate(., 'VALIDADE', 'validade'), 'validade') or contains(., 'Validade')]"),
        (By.XPATH, "//h6[contains(., '/') or contains(., '-') or contains(., 'até')]"),
        (By.XPATH, "//p[contains(., 'Validade') or contains(., '/') or contains(., 'até')]"),
    ]
    for by, xp in candidatos:
        try:
            elems = wait.until(EC.presence_of_all_elements_located((by, xp)))
            for e in elems:
                t = (e.text or "").strip()
                if t and (("valid" in t.lower()) or re.search(r"\d{1,2}[/-]\d{1,2}", t)):
                    return slugify(t)
        except:
            pass
    return "sem_validade"

def selecionar_loja(cidade: str):
    driver.get(BASE_URL)
    # select com class "select"
    select_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "select.select")))
    Select(select_element).select_by_visible_text(cidade)
    time.sleep(4)  # aguarda carregar os tabloids

def clicar_nas_imagens(pasta_destino: Path):
    imagens = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tabloids a")))
    print(f"{len(imagens)} tabloide(s) encontrado(s).")
    # abre até 2 em novas abas (ajuste se quiser mais)
    for i in range(min(2, len(imagens))):
        link = imagens[i].get_attribute("href")
        if not link:
            continue
        driver.execute_script("window.open(arguments[0], arguments[1]);", link, "_blank")
        time.sleep(1)

    abas = driver.window_handles
    # percorre as abas recém-abertas (aba 0 é a principal)
    for i in range(1, len(abas)):
        driver.switch_to.window(abas[i])
        time.sleep(5)

        # screenshot página 1
        arq1 = pasta_destino / f"NovoAtacarejo_{i}_pag1.png"
        driver.save_screenshot(str(arq1))
        print(f" Screenshot pág.1 salvo: {arq1}")

        # tenta ir para a página 2 (botão 'Next Page' do visualizador)
        try:
            next_button = wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "div.pdff-ui-btn.pdff-ui-next.pdff-ui-alt.fa.fa-chevron-right[title='Next Page']"
                ))
            )
            next_button.click()
            time.sleep(5)
            arq2 = pasta_destino / f"NovoAtacarejo_{i}_pag2.png"
            driver.save_screenshot(str(arq2))
            print(f" Screenshot pág.2 salvo: {arq2}")
        except Exception as e:
            print(f"Não foi possível capturar a pág.2 na aba {i}: {e}")

    # fecha abas extras e volta para a principal
    for i in range(1, len(abas)):
        try:
            driver.switch_to.window(abas[i])
            driver.close()
        except:
            pass
    driver.switch_to.window(abas[0])

def main():
    selecionar_loja(CIDADE)
    validade = detectar_validade()
    pasta_destino = OUT_BASE / slugify(CIDADE) / validade
    pasta_destino.mkdir(parents=True, exist_ok=True)
    print(f"Pasta de destino: {pasta_destino}")

    clicar_nas_imagens(pasta_destino)

    print("Finalizado.")

if __name__ == "__main__":
    try:
        main()
    finally:
        driver.quit()
