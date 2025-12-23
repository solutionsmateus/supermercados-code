import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from io import BytesIO

# === CONFIGURAÇÃO DE REDIMENSIONAMENTO ===
RESIZE_FACTOR = 2 # Este é o fator que dobra a resolução (2x)

# === CONFIGURAÇÃO DOS RECORTES (COORDENADAS E DIMENSÕES EXATAS) ===

# 1. Recorte Padrão (Para Páginas 1, 2, 4 e outras não-3)
# Dimensão: 626 x 853. Posição: 648, 17
CROP_PADRAO = [{
    "width": 626,
    "height": 853, 
    "x": 648,
    "y": 17,
    "suffix": ""
}]

# 2. Recorte Spread (APENAS PARA A PÁGINA 3)
# Dimensão: 1226 x 842. Posição: 348, 22
CROP_SPREAD_UNICO = [{
    "width": 1226,
    "height": 842,
    "x": 348,
    "y": 22,
    "suffix": "_spread"
}]

# Configurações do ambiente
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080
BASE_URL = "https://novoatacarejo.com/oferta/"
CIDADE = "Olinda"

# === SAÍDA PADRONIZADA ===
BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
OUT_BASE = BASE_OUTPUT / "Novo-Atacarejo"
OUT_BASE.mkdir(parents=True, exist_ok=True)
print(f"[novoatacarejo.py] Pasta base de saída: {OUT_BASE}")

def build_headless_chrome(download_dir: Path):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/555.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/555.36"
    )
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
    """ Tenta capturar uma indicação de validade/período. """
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
    select_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "select.select")))
    Select(select_element).select_by_visible_text(cidade)
    time.sleep(4)

def obter_numero_da_pagina() -> tuple[int, int]:
    """
    Lê o label 'X/Y' da barra de navegação do encarte e retorna X (página atual) e Y (total de páginas).
    """
    try:
        page_label = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.pdff-ui-page label[for='df_book_page_number']"
            ))
        )
        texto = page_label.text.split('/')
        page_number = int(texto[0].strip())
        total_pages = int(texto[1].strip())
        return page_number, total_pages
    except:
        print("Aviso: Não foi possível determinar o número da página ou o total. Assumindo 1/1.")
        return 1, 1

def cortar_e_salvar_screenshot(pasta_destino: Path, nome_base: str, crop_settings):
    """
    Captura a tela inteira, aplica o corte, redimensiona em 2x e salva.
    """
    try:
        png = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(png))

        for crop in crop_settings:
            w, h, x, y, suffix = crop["width"], crop["height"], crop["x"], crop["y"], crop["suffix"]

            # 1. Aplica o corte (crop)
            caixa_corte = (x, y, x + w, y + h)
            img_cortada = img.crop(caixa_corte)
            
            # 2. Redimensiona em 2x (aumenta a resolução)
            # ESTA PARTE GARANTE O DOBRO DA RESOLUÇÃO (2x) PARA QUALQUER CORTE.
            new_w = w * RESIZE_FACTOR
            new_h = h * RESIZE_FACTOR
            
            # Usa o filtro LANCZOS para melhor qualidade de upscaling (redimensionamento)
            try:
                img_redimensionada = img_cortada.resize((new_w, new_h), Image.Resampling.LANCZOS)
            except AttributeError:
                img_redimensionada = img_cortada.resize((new_w, new_h), Image.LANCZOS)
                
            # 3. Salva a imagem redimensionada
            nome_arquivo = f"{nome_base}{suffix}_2x.png"
            arq_saida = pasta_destino / nome_arquivo
            img_redimensionada.save(str(arq_saida))
            print(f" Screenshot recortado e REDIMENSIONADO 2X salvo: {arq_saida} (Original: {w}x{h}, Final: {new_w}x{new_h})")

    except Exception as e:
        print(f"Erro ao cortar, redimensionar e salvar o screenshot: {e}")


def clicar_nas_imagens(pasta_destino: Path):
    imagens = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tabloids a")))
    print(f"{len(imagens)} tabloide(s) encontrado(s).")
    
    for i in range(min(2, len(imagens))):
        link = imagens[i].get_attribute("href")
        if not link:
            continue
        driver.execute_script("window.open(arguments[0], arguments[1]);", link, "_blank")
        time.sleep(1)

    abas = driver.window_handles
    
    for i in range(1, len(abas)):
        driver.switch_to.window(abas[i])
        print(f"\nAcessando Tabloide {i}...")
        
        while True:
            try:
                next_button = wait.until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "div.pdff-ui-btn.pdff-ui-next.pdff-ui-alt.fa.fa-chevron-right[title='Next Page']"
                    ))
                )
                
                time.sleep(5) 

                page_number, total_pages = obter_numero_da_pagina()

                # LÓGICA CONDICIONAL DE RECORTE
                if page_number == 3:
                    recortes_atuais = CROP_SPREAD_UNICO
                    print(f"Capturando Página {page_number} de {total_pages} (APENAS PÁGINA 3 - Recorte Spread Único)...")
                else:
                    recortes_atuais = CROP_PADRAO
                    print(f"Capturando Página {page_number} de {total_pages} (Padrão - Recorte Único)...")
                
                nome_base = f"NovoAtacarejo_Enc{i}_pag{page_number}"
                cortar_e_salvar_screenshot(pasta_destino, nome_base, recortes_atuais)

                # Verifica se estamos na última página. Se sim, quebra o loop
                if page_number >= total_pages:
                    print(f"Última página ({page_number}/{total_pages}) capturada. Passando para o próximo tabloide.")
                    break
                
                # Avança para a próxima página
                next_button.click()
                
            except Exception as e:
                print(f"Finalizado o encarte {i}. Fim do documento ou erro no avanço. (Detalhe: {e})")
                break

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
    print(f"\nPasta de destino: {pasta_destino}")

    clicar_nas_imagens(pasta_destino)

    print("\nFinalizado.")

if __name__ == "__main__":
    try:
        main()
    finally:
        driver.quit()