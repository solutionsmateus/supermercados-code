import os
import time
import requests
import unicodedata
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re

# === SAÍDA PADRONIZADA (ARTIFACT) ============================================
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[assai.py] Pasta de saída: {OUTPUT_DIR}")
# ============================================================================

# Mapeamento Estado -> Nome da Loja
LOJAS_ESTADOS = {
    "Maranhão": "Assaí Angelim",
    "Alagoas": "Assaí Maceió Farol",
    "Ceará": "Assaí Bezerra M (Fortaleza)",
    "Pará": "Assaí Belém",
    "Paraíba": "Assaí João Pessoa Geisel",
    "Pernambuco": "Assaí Avenida Recife",
    "Piauí": "Assaí Teresina",
    "Sergipe": "Assaí Aracaju",
    "Bahia": "Assaí Vitória da Conquista",
}

# Região preferida por estado (quando o site exibe select.regiao)
REGIAO_POR_ESTADO = {"Bahia": "Interior"}

BASE_URL = "https://www.assai.com.br/ofertas"

# === Helpers de normalização/clique ==========================================
def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()

def click_robusto(driver, el) -> bool:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)
        el.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

# === HEADLESS CHROME =========================================================
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
wait = WebDriverWait(driver, 30)

# === HELPERS =================================================================
def encontrar_data():
    # pega qualquer bloco de "validade"
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class,"ofertas-tab-validade")]'))
        )
    except:
        return "sem_data"
    for div in enc_data:
        texto = (div.text or "").strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]+', '_', texto)
            return nome_pasta[:80]
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR):
    element = wait.until(EC.element_to_be_clickable((by, seletor)))
    if not click_robusto(driver, element):
        raise RuntimeError(f"Não consegui clicar em: {seletor}")

def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.4)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.4)

def select_contains_noaccent(select_el, target_text, timeout=10) -> bool:
    WebDriverWait(driver, timeout).until(lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 0)
    alvo = strip_accents(target_text)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    for o in opts:
        if alvo in strip_accents(o.text):
            Select(select_el).select_by_visible_text(o.text)
            return True
    return False

def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()
    download_dir.mkdir(parents=True, exist_ok=True)

    # sessão com headers (evita alguns bloqueios)
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": driver.current_url
    })

    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        links_download = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@class,'download') and contains(@href,'.jpeg')]")
            )
        )
        current_page_urls = []
        for link in links_download:
            url = link.get_attribute("href")
            if url and url not in downloaded_urls:
                current_page_urls.append(url)
                downloaded_urls.add(url)

        if not current_page_urls and page_num > 1:
            break

        for idx, url in enumerate(current_page_urls, start=1):
            try:
                response = sess.get(url, timeout=30)
                if response.status_code == 200 and response.content:
                    file_path = download_dir / f"encarte_j{jornal_num}_p{page_num}_{idx}_{int(time.time())}.jpg"
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    print(f"  Encarte salvo: {file_path}")
                else:
                    print(f"  Falha no download: {url} (HTTP {response.status_code})")
            except Exception as e:
                print(f"  Erro ao baixar {url}: {e}")

        # próxima página do slider
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
            time.sleep(0.3)
            if not click_robusto(driver, next_button):
                break
            time.sleep(2)
            page_num += 1
        except:
            break

# === MAIN ====================================================================
try:
    driver.get(BASE_URL)
    time.sleep(2)

    # Fecha eventual popup de cookies
    try:
        clicar_elemento("button.ot-close-icon")
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f" Processando: {estado} - {loja}")

        # Estado: tenta exato e cai para "contém" sem acentos
        estado_select = aguardar_elemento("select.estado")
        try:
            Select(estado_select).select_by_visible_text(estado)
        except:
            ok = select_contains_noaccent(estado_select, estado)
            if not ok:
                raise RuntimeError(f"Estado '{estado}' não encontrado")

        time.sleep(0.8)

        # Região (quando existir)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select = aguardar_elemento("select.regiao", timeout=15)
                ok = select_contains_noaccent(regiao_select, REGIAO_POR_ESTADO[estado])
                if not ok:
                    print(f"  Aviso: região '{REGIAO_POR_ESTADO[estado]}' não encontrada para {estado}")
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.4)
            except Exception as e:
                print(f" Não foi possível selecionar a região para {estado}: {e}")

        # Loja (tenta exato e cai para contém/sem acento)
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            ok = select_contains_noaccent(loja_select, loja)
            if not ok:
                raise RuntimeError(f"Não encontrei a loja '{loja}' no estado {estado}")

        time.sleep(0.6)

        # Confirmar
        clicar_elemento("button.confirmar")
        time.sleep(1)

        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()

        nome_loja = re.sub(r'[\\/*?:"<>|\s]+', '_', loja)
        pasta_loja_data = OUTPUT_DIR / f"assai_{nome_loja}_{data_nome}"
        pasta_loja_data.mkdir(parents=True, exist_ok=True)
        print(f"  Salvando em: {pasta_loja_data}")

        scroll_down_and_up()
        baixar_encartes(1, pasta_loja_data)

        # Tenta "Jornal de Ofertas 2..3"
        for i in range(2, 4):
            try:
                # botão por XPath com contains
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                scroll_down_and_up()
                baixar_encartes(i, pasta_loja_data)
            except Exception as e:
                print(f" Jornal {i} indisponível para {loja}: {str(e)}")

        # Volta ao seletor para próximo estado
        clicar_elemento("a.seletor-loja")
        time.sleep(1.2)

    print("Todos os encartes foram processados!")

except Exception as e:
    print(f"Erro crítico: {str(e)}")
    try:
        (OUTPUT_DIR / "debug").mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str((OUTPUT_DIR / "debug" / "erro_encartes.png").resolve()))
        print(f"Screenshot de erro salvo em: {(OUTPUT_DIR / 'debug' / 'erro_encartes.png').resolve()}")
    except Exception:
        pass
finally:
    driver.quit()
