import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = BASE_OUTPUT / "Atakarejo"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"📦 [atakarejo.py] Pasta base de saída: {ENCARTE_DIR}")

CIDADES_ALVO = [
    {
        "nome": "Vitoria-da-Conquista",
        "url": "https://atakarejo.com.br/cidade/vitoria-da-conquista",
    },
    {
        "nome": "Salvador",
        "url": "https://atakarejo.com.br/cidades/salvador/",
    },
]

def build_headless_chrome():
    """Configura e retorna uma instância do Chrome em modo headless."""
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

def slugify(s: str) -> str:
    s = re.sub(r"[\\/*?:\"<>|\r\n]+", "_", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:80] if s else "sem_data"

def encontrar_data_validade(driver, wait) -> str:
    candidatos = [
        (By.XPATH, "//h3[contains(translate(., 'VALIDEADE', 'valideade'), 'validade') or contains(., 'Validade')]"),
        (By.XPATH, "//p[contains(., 'Validade') or contains(., 'VALIDADE')]"),
        (By.XPATH, "//div[contains(@class,'validade') or contains(@class,'oferta')]/descendant::*[self::p or self::h3]"),
    ]
    for by, xp in candidatos:
        try:
            elems = wait.until(EC.presence_of_all_elements_located((by, xp)))
            for e in elems:
                txt = (e.text or "").strip()
                if txt and ("validade" in txt.lower() or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", txt)):
                    return slugify(txt)
        except:
            pass

    try:
        body = driver.find_element(By.TAG_NAME, "body").text
        m = re.search(r"(validade.*?)(\d{1,2}/\d{1,2}/\d{2,4}.*)$", body, flags=re.I | re.S)
        if m:
            return slugify(m.group(0))
    except:
        pass

    return "sem_data"

def baixar_pdf(url: str, destino: Path):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(destino, "wb") as f:
            f.write(resp.content)
        print(f"Baixado: {destino.name}")
    except Exception as e:
        print(f"Erro ao baixar {url}: {e}")

def processar_cidade(driver, wait, cidade_info: dict):
    """Executa o processo de busca e download para uma cidade específica."""
    cidade_nome = cidade_info["nome"]
    url_cidade = cidade_info["url"]

    print(f"\n---Processando cidade: **{cidade_nome}** ({url_cidade}) ---")

    try:
        driver.get(url_cidade)

        # Espera pelos links de download
        links = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, '//a[contains(@class, "button-download-ofertas") or contains(@href, ".pdf")]')
        ))
        print(f"{len(links)} encarte(s) encontrado(s) na página.")

        validade_slug = encontrar_data_validade(driver, wait)
        
        # Cria a pasta de destino com Cidade/Validade
        pasta_destino = (ENCARTE_DIR / cidade_nome / validade_slug)
        pasta_destino.mkdir(parents=True, exist_ok=True)
        print(f"Pasta de destino: {pasta_destino.relative_to(BASE_OUTPUT)}")

        vistos = set()
        for i, link in enumerate(links, start=1):
            url_pdf = link.get_attribute("href")
            if not url_pdf or not url_pdf.endswith(".pdf") or url_pdf in vistos:
                continue
            vistos.add(url_pdf)

            nome = f"encarte_{i}.pdf"
            caminho = pasta_destino / nome
            print(f" Tentando baixar encarte {i}/{len(links)}...")
            baixar_pdf(url_pdf, caminho)

    except Exception as e:
        print(f"  Erro ao processar {cidade_nome}: {e}")
        time.sleep(2)




driver = build_headless_chrome()
wait = WebDriverWait(driver, 20)

try:
    for cidade in CIDADES_ALVO:
        processar_cidade(driver, wait, cidade)

except Exception as e:
    print(f"\nErro geral inesperado: {e}")

finally:
    print("\nExecução finalizada.")
    driver.quit()