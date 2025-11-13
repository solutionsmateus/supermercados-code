import os
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re

# === CONFIGURAÇÕES ===
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

REGIAO_POR_ESTADO = {
    "Bahia": "Interior",
}

BASE_URL = "https://www.assai.com.br/ofertas"

# CI-FRIENDLY: Usa workspace do GitHub Actions
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/github/workspace/encartes"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === HEADLESS CHROME ===
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--lang=pt-BR,pt")
    return webdriver.Chrome(options=options)

try:
    driver = build_headless_chrome()
except Exception as e:
    print(f"Erro ao inicializar Chrome: {e}")
    exit(1)

wait = WebDriverWait(driver, 30)

# === FUNÇÕES AUXILIARES ===
def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
        for div in enc_data:
            texto = div.text.strip()
            if texto:
                return re.sub(r'[\\/*?:"<>|\s]', '_', texto)
    except:
        pass
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR, timeout=30):
    element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", element)
    time.sleep(0.5)
    element.click()

def select_by_visible_text_contains(select_el, target_text):
    sel = Select(select_el)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    alvo = target_text.strip().lower()
    for o in opts:
        if alvo in o.text.strip().lower():
            sel.select_by_visible_text(o.text)
            return True
    return False

# === DOWNLOAD DE ENCARTE (CARROSSEL) ===
def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()

    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")

        # Força lazy-load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        # ESPERA O LINK DO ENCARTE (não a imagem!)
        try:
            links = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, """
                        //div[contains(@class, 'slick-active')]//a[
                            contains(@href, 'campanha') and 
                            contains(@href, 'pagina') and 
                            (contains(@href, '.jpeg') or contains(@href, '.jpg'))
                        ]
                    """)
                )
            )
        except:
            if page_num > 1:
                print("  Nenhum link de encarte encontrado. Fim do carrossel.")
                break
            links = []

        current_urls = []
        for link in links:
            url = link.get_attribute("href")
            if url and url not in downloaded_urls:
                current_urls.append(url)
                downloaded_urls.add(url)

        if not current_urls and page_num > 1:
            break

        # DOWNLOAD DOS ENCARTES
        for idx, url in enumerate(current_urls, 1):
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    # Detecta extensão real
                    ext = ".jpeg" if "jpeg" in url.lower() else ".jpg"
                    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
                    filename = f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{ts}{ext}"
                    path = download_dir / filename
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    print(f"    [ENCA] {path.name}")
                else:
                    print(f"    [X] Falha {resp.status_code}: {url}")
            except Exception as e:
                print(f"    [Erro] {url}: {e}")

        # AVANÇA O CARROSSEL
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button.slick-next:not(.slick-disabled)")
            if not next_btn.is_enabled():
                print("  Botão Next desabilitado.")
                break

            driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", next_btn)
            time.sleep(0.8)
            driver.execute_script("arguments[0].click();", next_btn)

            # Espera novo encarte carregar
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'slick-active')]//a[contains(@href, 'campanha')]")
                )
            )
            time.sleep(2.5)
            page_num += 1

        except Exception as e:
            print(f"  Fim do carrossel: {e}")
            break

        # Avançar carrossel
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button.slick-next:not(.slick-disabled)")
            if not next_btn.is_enabled():
                print("  Botão Next desabilitado.")
                break

            driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", next_btn)
            time.sleep(0.8)
            driver.execute_script("arguments[0].click();", next_btn)  # JS click

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'slick-slide slick-current slick-active')]//img[contains(@src, 'jpeg')]")
                )
            )
            time.sleep(2.5)
            page_num += 1

        except Exception as e:
            print(f"  Fim do carrossel: {e}")
            break

# === MAIN ===
try:
    driver.get(BASE_URL)
    time.sleep(3)

    # Fecha popup
    try:
        clicar_elemento("button.ot-close-icon", timeout=5)
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f"\n--- Processando: {estado} - {loja} ---")

        # 1. Estado
        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # 2. Região (se aplicável)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f"  Região não selecionada: {e}")

        # 3. Loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            if not select_by_visible_text_contains(loja_select, loja):
                raise RuntimeError(f"Loja não encontrada: {loja}")

        time.sleep(0.8)

        # 4. Confirmar
        clicar_elemento("button.confirmar")
        time.sleep(3)

        # 5. Raspagem
        aguardar_elemento("div.slick-slide slick-current slick-active", timeout=30)
        data_nome = encontrar_data()
        nome_loja = re.sub(r'[\\/*?:"<>|\s]', '_', loja)
        download_dir = OUTPUT_DIR / f"encartes_{nome_loja}_{data_nome}"
        download_dir.mkdir(parents=True, exist_ok=True)

        # Primeiro jornal
        baixar_encartes(1, download_dir)

        # Jornais 2 e 3
        for i in range(2, 4):
            try:
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.slick-slide slick-current slick-active", timeout=30)
                baixar_encartes(i, download_dir)
            except Exception as e:
                print(f"  Jornal {i} não disponível: {e}")

        # Voltar ao seletor
        try:
            clicar_elemento("a.seletor-loja")
            time.sleep(2)
        except:
            pass

    print("\nTodos os encartes foram processados!")

except Exception as e:
    print(f"\nERRO CRÍTICO: {e}")
    try:
        screenshot_path = OUTPUT_DIR / "ERRO_assai.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"  Screenshot salvo: {screenshot_path}")
    except:
        pass
finally:
    driver.quit()
