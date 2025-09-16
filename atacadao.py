import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# === SAÍDA PADRONIZADA (ARTIFACT) ============================================
# Lê do ambiente (OUTPUT_DIR), senão usa ./Encartes
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
    "MA": ("São Luís", "São Luís")
}

BASE_URL = "https://www.atacadao.com.br/institucional/nossas-lojas"

# === CHROME HEADLESS ===
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
wait = WebDriverWait(driver, 20)

def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//p[contains(@class, "text-xs text-neutral-400")]')
            )
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def clicar_confirmar():
    try:
        confirmar_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Confirmar']"))
        )
        confirmar_button.click()
    except:
        pass

def selecionar_uf_cidade(uf, cidade):
    Select(
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//select[contains(@class, 'md:w-[96px]')]")
        ))
    ).select_by_value(uf)
    time.sleep(1)
    Select(
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//select[contains(@class, 'md:w-[360px]')]")
        ))
    ).select_by_visible_text(cidade)
    time.sleep(1)

def clicar_loja_por_nome(loja_nome):
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='store-card']")))
    lojas = driver.find_elements(By.CSS_SELECTOR, "[data-testid='store-card']")
    for loja in lojas:
        try:
            titulo = loja.find_element(By.TAG_NAME, "h1").text
            if loja_nome.lower() in titulo.lower():
                botao = loja.find_element(By.TAG_NAME, "a")
                print(f"Acessando loja: {titulo}")
                botao.click()
                return titulo
        except:
            continue
    print(f" Loja '{loja_nome}' não encontrada.")
    return None

def baixar_encartes(uf, cidade, loja_nome):
    print("Buscando encartes...")
    try:
        time.sleep(2)
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'Flyer/?id=')]")

        if not links:
            print("Nenhum link de encarte encontrado.")
            return

        loja_segura = re.sub(r'[\\/*?:"<>|,\n\r]+', "_", loja_nome).strip().replace(" ", "_")
        pasta_destino = ENCARTE_DIR / uf / cidade / loja_segura
        pasta_destino.mkdir(parents=True, exist_ok=True)

        for i, link in enumerate(links, start=1):
            url = link.get_attribute("href")
            if not url:
                continue
            nome_arquivo = f"encarte_{i}.pdf"
            caminho = pasta_destino / nome_arquivo

            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                with open(caminho, "wb") as f:
                    f.write(response.content)
                print(f" Baixado: {nome_arquivo}")
            except Exception as e:
                print(f"Erro ao baixar {url}: {e}")

    except Exception as e:
        print(f"Erro ao buscar encartes: {e}")

try:
    driver.get(BASE_URL)
    clicar_confirmar()

    for uf, (cidade, loja_nome) in LOJAS_ESTADOS.items():
        print(f"\n Estado: {uf} | Cidade: {cidade} | Loja: {loja_nome}")
        driver.get(BASE_URL)
        time.sleep(2)
        clicar_confirmar()

        selecionar_uf_cidade(uf, cidade)
        nome_loja_encontrada = clicar_loja_por_nome(loja_nome)

        if nome_loja_encontrada:
            baixar_encartes(uf, cidade, nome_loja_encontrada)
            time.sleep(1)

except Exception as e:
    print(f" Erro geral: {e}")

finally:
    print(" Execução finalizada")
    driver.quit()
