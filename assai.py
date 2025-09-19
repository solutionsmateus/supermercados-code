import os
import time
import re
from pathlib import Path
from datetime import datetime

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# ============================= Config/Geral =============================

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[assai.py] Pasta de saída: {OUTPUT_DIR}")

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

# ====================== Sessão requests com cookies =====================

def make_session_from_driver(driver, extra_headers=None):
    """Cria uma requests.Session reaproveitando cookies do Selenium."""
    s = requests.Session()
    retries = Retry(
        total=4,
        connect=3,
        read=3,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))

    s.headers.update({
        "User-Agent": os.getenv("HTTP_UA", DEFAULT_UA),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
    })
    if extra_headers:
        s.headers.update(extra_headers)

    # Copia cookies do Selenium (removendo ponto inicial do domínio)
    for c in driver.get_cookies():
        s.cookies.set(
            name=c.get("name"),
            value=c.get("value"),
            domain=(c.get("domain") or "").lstrip(".") or None,
            path=c.get("path", "/"),
        )
    return s

def download_with_session(session, url, dest, referer):
    """Baixa a URL usando a session (com cookies) e Referer, tratando 403."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Referer": referer}

    r = session.get(url, headers=headers, timeout=40, stream=True)
    if r.status_code == 403:
        # Tenta header alternativo
        alt_headers = dict(headers)
        alt_headers["Accept"] = "*/*"
        alt_headers["Accept-Encoding"] = "identity"
        time.sleep(1.0)
        r = session.get(url, headers=alt_headers, timeout=40, stream=True)

    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} baixando {url}")

    with open(dest, "wb") as f:
        for chunk in r.iter_content(128 * 1024):
            if chunk:
                f.write(chunk)
    return dest

# ============================= Selenium =================================

def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(f"--user-agent={DEFAULT_UA}")
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
wait = WebDriverWait(driver, 30)

# ============================== Helpers =================================

def encontrar_data():
    """Extrai o texto de validade exibido no topo das ofertas."""
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
    except Exception:
        return "sem_data"
    for div in enc_data:
        texto = (div.text or "").strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]+', '_', texto)
            return nome_pasta[:80]
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, seletor))
    )

def clicar_elemento(seletor, by=By.CSS_SELECTOR):
    element = wait.until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()

def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.5)

def select_by_visible_text_contains(select_el, target_text, timeout=10):
    WebDriverWait(driver, timeout).until(
        lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 0
    )
    sel = Select(select_el)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    alvo_norm = (target_text or "").strip().lower()
    for o in opts:
        if alvo_norm in o.text.strip().lower():
            sel.select_by_visible_text(o.text)
            return True
    return False

def baixar_encartes(jornal_num: int, download_dir: Path, session: requests.Session):
    """Percorre as páginas do slider e baixa as imagens .jpeg exibidas."""
    page_num = 1
    downloaded_urls = set()
    download_dir.mkdir(parents=True, exist_ok=True)

    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        links_download = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@class, 'download') and contains(@href, '.jpeg')]")
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

        referer_url = driver.current_url  # fundamental para CloudFront
        for idx, url in enumerate(current_page_urls, start=1):
            try:
                filename = f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{int(time.time())}.jpg"
                file_path = download_dir / filename
                download_with_session(session, url, file_path, referer=referer_url)
                print(f"  Encarte salvo: {file_path}")
            except Exception as e:
                print(f"  Falha no download: {url} ({e})")

        # próxima página do slider
        try:
            next_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.5)
            next_button.click()
            time.sleep(2)
            page_num += 1
        except Exception:
            break

# ================================ Main ==================================

try:
    driver.get(BASE_URL)
    time.sleep(2)

    # Fecha eventual popup de cookies
    try:
        clicar_elemento("button.ot-close-icon")
    except Exception:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f" Processando: {estado} - {loja}")

        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # Seletor de Região (quando existir)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select_element = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select_element).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f" Não foi possível selecionar a região para {estado}: {e}")

        # Seleção da loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except Exception:
            ok = select_by_visible_text_contains(loja_select, loja)
            if not ok:
                raise RuntimeError(f"Não encontrei a loja '{loja}' no estado {estado}")

        time.sleep(0.8)

        clicar_elemento("button.confirmar")
        time.sleep(1)

        # Garante que o slider carregou e extrai texto de validade
        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()

        # Cria a sessão APÓS carregar o slider (cookies corretos)
        sess = make_session_from_driver(driver)

        # Pasta de saída por loja+data (sanitizada)
        nome_loja = re.sub(r'[\\/*?:"<>|\s]+', '_', loja)
        pasta_loja_data = OUTPUT_DIR / f"assai_{nome_loja}_{data_nome}"
        pasta_loja_data.mkdir(parents=True, exist_ok=True)
        print(f"  Salvando em: {pasta_loja_data}")

        scroll_down_and_up()

        # Jornal 1
        baixar_encartes(1, pasta_loja_data, session=sess)

        # Tenta "Jornal de Ofertas 2..3"
        for i in range(2, 4):
            try:
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                scroll_down_and_up()
                baixar_encartes(i, pasta_loja_data, session=sess)
            except Exception as e:
                print(f" Jornal {i} indisponível para {loja}: {str(e)}")

        # Volta ao seletor para próximo estado
        clicar_elemento("a.seletor-loja")
        time.sleep(2)

    print("Todos os encartes foram processados!")

except Exception as e:
    print(f"Erro crítico: {str(e)}")
    try:
        # Mesmo em headless conseguimos salvar screenshot para debug
        (OUTPUT_DIR / "debug").mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str((OUTPUT_DIR / "debug" / "erro_encartes.png").resolve()))
        print(f"Screenshot de erro salvo em: {(OUTPUT_DIR / 'debug' / 'erro_encartes.png').resolve()}")
    except Exception:
        pass
finally:
    driver.quit()
