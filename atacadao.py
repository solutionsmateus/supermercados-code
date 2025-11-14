import os
import re
import time
import unicodedata
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# === SAÍDA PADRONIZADA (ARTIFACT) ============================================
BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = BASE_OUTPUT / "Atacadao"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[atacadao.py] Pasta de saída: {ENCARTE_DIR}")
# ============================================================================

LOJAS_ESTADOS = {
    "AL": ("Maceió", "Maceió Praia"),
    "CE": ("Fortaleza", "Fortaleza Fátima"),
    "PA": ("Belém", "Belém Portal da Amazônia"),
    "PB": ("João Pessoa", "João Pessoa Bessa"),
    "PE": ("Recife", "Recife Avenida Recife"),
    "PI": ("Teresina", "Teresina Primavera"),
    "SE": ("Aracaju", "Aracaju Tancredo Neves"),
    "BA": ("Vitória Da Conquista", "Vitória da Conquista"),
    "MA": ("São Luís", "São Luís"),
}

BASE_URL = "https://www.atacadao.com.br/institucional/nossas-lojas"

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
wait = WebDriverWait(driver, 25)

def clicar_confirmar():
    try:
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Confirmar']")))
        click_robusto(driver, btn)
        time.sleep(0.4)
    except Exception:
        pass

def selecionar_uf_cidade(uf: str, cidade: str):
    uf_sel = wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'md:w-[96px]')]")))
    Select(uf_sel).select_by_value(uf)
    time.sleep(0.6)

    cid_sel = wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'md:w-[360px]')]")))
    alvo = strip_accents(cidade)
    try:
        Select(cid_sel).select_by_visible_text(cidade)
    except Exception:
        opts = cid_sel.find_elements(By.TAG_NAME, "option")
        escolha = None
        for o in opts:
            if alvo in strip_accents(o.text):
                escolha = o.text
                break
        if not escolha:
            raise RuntimeError(f"Cidade '{cidade}' não encontrada para UF {uf}")
        Select(cid_sel).select_by_visible_text(escolha)
    time.sleep(0.8)

def clicar_loja_por_nome(loja_nome: str):
    alvo = strip_accents(loja_nome)
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='store-card']")))
    cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='store-card']")
    for card in cards:
        try:
            titulo_el = card.find_element(By.TAG_NAME, "h1")
            titulo = titulo_el.text
            if alvo in strip_accents(titulo):
                botao = card.find_element(By.TAG_NAME, "a")
                print(f"Acessando loja: {titulo}")
                if click_robusto(driver, botao):
                    return titulo
        except Exception:
            continue
    print(f" Loja '{loja_nome}' não encontrada.")
    return None

def baixar_encartes(uf: str, cidade: str, loja_nome: str):
    print("Buscando encartes...")
    time.sleep(2)

    links = driver.find_elements(By.XPATH, "//a[contains(@href, 'Flyer/?id=')]")
    if not links:
        print("Nenhum link de encarte encontrado.")
        return

    loja_segura = re.sub(r'[\\/*?:"<>|,\n\r]+', "_", loja_nome).strip().replace(" ", "_")
    pasta_destino = ENCARTE_DIR / uf / cidade / loja_segura
    pasta_destino.mkdir(parents=True, exist_ok=True)

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": driver.current_url, 
    })

    vistos = set()
    for i, link in enumerate(links, start=1):
        url = link.get_attribute("href")
        if not url or url in vistos:
            continue
        vistos.add(url)

        nome_arquivo = f"encarte_{i}.pdf"
        caminho = pasta_destino / nome_arquivo
        try:
            r = sess.get(url, timeout=40)
            r.raise_for_status()
            with open(caminho, "wb") as f:
                f.write(r.content)
            print(f" Baixado: {caminho}")
        except Exception as e:
            print(f"Erro ao baixar {url}: {e}")

try:
    driver.get(BASE_URL)
    clicar_confirmar()

    for uf, (cidade, loja_nome) in LOJAS_ESTADOS.items():
        print(f"\n Estado: {uf} | Cidade: {cidade} | Loja: {loja_nome}")
        driver.get(BASE_URL)
        time.sleep(1.5)
        clicar_confirmar()

        selecionar_uf_cidade(uf, cidade)
        loja_encontrada = clicar_loja_por_nome(loja_nome)

        if loja_encontrada:
            baixar_encartes(uf, cidade, loja_encontrada)
            time.sleep(0.5)

except Exception as e:
    print(f" Erro geral: {e}")

finally:
    print(" Execução finalizada")
    driver.quit()
