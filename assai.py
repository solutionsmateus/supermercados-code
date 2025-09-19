import os
import time
import re
import random
from pathlib import Path

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

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
        total=4, connect=3, read=3, backoff_factor=1.2,
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

def _headers_img(referer):
    return {
        "Referer": referer,
        "Origin": "https://www.assai.com.br",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Dest": "image",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

def wait_url_live(session, url, referer, timeout=12):
    """Espera a URL responder 200 (GET leve) — útil quando o CDN 'demora a liberar'."""
    end = time.time() + timeout
    headers = _headers_img(referer)
    while time.time() < end:
        try:
            r = session.get(url, headers=headers, timeout=8, stream=True)
            code = r.status_code
            r.close()
            if code == 200:
                return True
            if code == 403:
                headers["Referer"] = "https://www.assai.com.br/ofertas"
        except Exception:
            pass
        time.sleep(0.5 + random.random()*0.6)
    return False

def download_with_session(session, url, dest, referer):
    """Baixa a URL usando a session (com cookies) e headers de navegador; trata 403."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = _headers_img(referer)

    wait_url_live(session, url, referer, timeout=10)

    r = session.get(url, headers=headers, timeout=40, stream=True)
    if r.status_code == 403:
        headers["Referer"] = "https://www.assai.com.br/ofertas"
        time.sleep(0.6 + random.random()*0.4)
        r = session.get(url, headers=headers, timeout=40, stream=True)

    if r.status_code == 403:
        headers["Accept"] = "*/*"
        headers["Accept-Encoding"] = "identity"
        time.sleep(0.6 + random.random()*0.5)
        r = session.get(url, headers=headers, timeout=40, stream=True)

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
    # downloads automáticos (fallback via navegador, se necessário)
    prefs = {
        "download.default_directory": str(OUTPUT_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
wait = WebDriverWait(driver, 50)  # mais folga

def set_download_dir(download_dir: Path):
    download_dir.mkdir(parents=True, exist_ok=True)
    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)}
        )
    except Exception:
        try:
            driver.execute_cdp_cmd(
                "Browser.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(download_dir)}
            )
        except Exception:
            pass

def wait_new_file(dirpath: Path, before: set, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        now = set(p for p in dirpath.glob("*") if p.is_file())
        new = [p for p in now - before if not p.name.endswith(".crdownload")]
        if new:
            return sorted(new, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        time.sleep(0.3)
    return None

# ============================== Helpers =================================

def encontrar_data():
    """Extrai o texto de validade exibido no topo das ofertas."""
    try:
        enc_data = WebDriverWait(driver, 20).until(
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

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=25):
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
    time.sleep(0.5 + random.random()*0.5)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.5 + random.random()*0.5)

def select_by_visible_text_contains(select_el, target_text, timeout=15):
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

def ensure_slider_ready(timeout=30):
    """Garante que o slider está visível e existem âncoras de download no DOM."""
    cont = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cont)
    time.sleep(0.8)
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider div.slick-slide.slick-active"))
    )
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider a.download"))
    )
    return cont

def _collect_active_download_hrefs():
    """Coleta HREFs só do slide ativo (ou current) — tolera variações do Slick."""
    els = driver.find_elements(By.CSS_SELECTOR,
        "div.ofertas-slider div.slick-slide.slick-active a.download[href$='.jpeg']"
    )
    if not els:
        els = driver.find_elements(By.CSS_SELECTOR,
            "div.ofertas-slider div.slick-slide.slick-current a.download[href$='.jpeg']"
        )
    pairs = []
    for a in els:
        try:
            href = a.get_attribute("href")
            if href:
                pairs.append((a, href))
        except WebDriverException:
            pass
    return pairs

def _wait_slide_changed(prev_hrefs, timeout=16):
    """Espera o slide ativo mudar (hrefs diferentes dos anteriores)."""
    end = time.time() + timeout
    prevset = {h for _, h in prev_hrefs}
    while time.time() < end:
        cur = _collect_active_download_hrefs()
        curset = {h for _, h in cur}
        if curset and curset != prevset:
            return cur
        time.sleep(0.4 + random.random()*0.4)
    return _collect_active_download_hrefs()

def baixar_encartes(jornal_num: int, download_dir: Path, session: requests.Session):
    """Percorre as páginas do slider e baixa as imagens; robusto a timing.
       Tenta via requests; em 403, fallback: baixa clicando no link com o navegador."""
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
        set_download_dir(download_dir)
        ensure_slider_ready(timeout=40)
    except Exception as e:
        print(f"  [jornal {jornal_num}] slider não ficou pronto: {e}")
        return

    page_num = 1
    downloaded = set()

    # primeira coleta do slide ativo (com tolerância)
    try:
        current = _collect_active_download_hrefs()
    except Exception as e:
        print(f"  [jornal {jornal_num}] falha coletando links: {e}")
        return

    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        referer_url = driver.current_url

        # Se ainda não há links, tenta reassegurar o slider
        if not current:
            try:
                ensure_slider_ready(timeout=20)
                current = _collect_active_download_hrefs()
            except Exception:
                pass
            if not current:
                print(f"  [jornal {jornal_num}] sem links de download nesta página — encerrando.")
                break

        for idx, (a_el, url) in enumerate(current, start=1):
            if url in downloaded:
                continue
            downloaded.add(url)

            filename = f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{int(time.time())}.jpg"
            file_path = download_dir / filename
            try:
                if not wait_url_live(session, url, referer_url, timeout=10):
                    time.sleep(0.6)
                download_with_session(session, url, file_path, referer=referer_url)
                print(f"  OK (requests): {url} -> {file_path}")
            except Exception as e1:
                # fallback: tentar baixar pelo navegador
                try:
                    before = set(p for p in download_dir.glob("*") if p.is_file())
                    driver.execute_script("window.open(arguments[0].href, '_blank');", a_el)
                    newf = wait_new_file(download_dir, before, timeout=50)
                    if not newf:
                        raise RuntimeError("timeout aguardando download via navegador")
                    try:
                        newf.replace(file_path)
                    except Exception:
                        data = newf.read_bytes()
                        file_path.write_bytes(data)
                        newf.unlink(missing_ok=True)
                    print(f"  OK (browser): {url} -> {file_path}")
                except Exception as e2:
                    print(f"  Falha no download: {url} (requests: {e1}; browser: {e2})")

        # próxima página do slider
        try:
            prev = current
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.4 + random.random()*0.3)
            next_button.click()
            current = _wait_slide_changed(prev, timeout=18)
            if not current or {h for _, h in current} == {h for _, h in prev}:
                break
            page_num += 1
            time.sleep(0.9 + random.random()*0.5)  # tempo pro lazy-load
        except Exception as e:
            print(f"  [jornal {jornal_num}] não consegui avançar slide: {e}")
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
                regiao_select_element = aguardar_elemento("select.regiao", timeout=25)
                Select(regiao_select_element).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=30)
                time.sleep(0.6)
            except Exception as e:
                print(f" Não foi possível selecionar a região para {estado}: {e}")

        # Seleção da loja
        loja_select = aguardar_elemento("select.loja", timeout=30)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except Exception:
            ok = select_by_visible_text_contains(loja_select, loja)
            if not ok:
                print(f"  Loja '{loja}' não encontrada em {estado} — pulando.")
                continue

        time.sleep(0.9)

        clicar_elemento("button.confirmar")
        time.sleep(1.2)

        # Garante que o slider carregou e extrai texto de validade
        aguardar_elemento("div.ofertas-slider", timeout=45)
        data_nome = encontrar_data()

        # Cria a sessão APÓS carregar o slider (cookies corretos) e aquece
        sess = make_session_from_driver(driver)
        try:
            sess.get(driver.current_url, timeout=15)
        except Exception:
            pass
        time.sleep(1.0)

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
                time.sleep(1.2)
                aguardar_elemento("div.ofertas-slider", timeout=45)
                scroll_down_and_up()

                # Re-sincroniza cookies da sessão a cada troca de jornal
                sess = make_session_from_driver(driver)
                try:
                    sess.get(driver.current_url, timeout=15)
                except Exception:
                    pass
                time.sleep(0.7)

                baixar_encartes(i, pasta_loja_data, session=sess)
            except Exception as e:
                print(f" Jornal {i} indisponível para {loja}: {str(e)}")

        # Volta ao seletor para próximo estado
        clicar_elemento("a.seletor-loja")
        time.sleep(1.5)

    print("Todos os encartes foram processados!")

except Exception as e:
    print(f"Erro crítico: {str(e)}")
    try:
        (OUTPUT_DIR / "debug").mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str((OUTPUT_DIR / "debug" / "erro_encartes.png").resolve()))
        with open(OUTPUT_DIR / "debug" / "page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Screenshot/HTML salvos em: {(OUTPUT_DIR / 'debug').resolve()}")
    except Exception:
        pass
finally:
    driver.quit()
