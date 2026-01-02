import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from io import BytesIO


RESIZE_FACTOR = 2

CROP_PADRAO = [{
    "width": 557,
    "height": 789,
    "x": 681,
    "y": 41,
    "suffix": ""
}]

# 2. Recorte Spread (Páginas Duplas: 1101x799 @ 410, 34)
CROP_SPREAD_UNICO = [{
    "width": 1101,
    "height": 799,
    "x": 410,
    "y": 34,
    "suffix": "_spread"
}]

BASE_URL = "https://cometasupermercados.com.br/ofertas/"

BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = (BASE_OUTPUT / "Cometa-Supermercados")
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[cometa.py] Pasta base de saída: {ENCARTE_DIR}")

def iniciar_driver():
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
    prefs = {
        "download.prompt_for_download": False,
        "download.default_directory": str(ENCARTE_DIR),
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60) # Adicione esta linha!
    return driver


def obter_numero_e_tipo_pagina(wait: WebDriverWait) -> tuple[int, bool]:
    try:
        page_label = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.flipbook-currentPageNumber"
            ))
        )
        texto = page_label.text.split('/')[0].strip()
        
        if '-' in texto:
            primeira_pagina = int(texto.split('-')[0].strip())
            is_spread = True
        else:
            # Página única (ex: "1")
            primeira_pagina = int(texto)
            is_spread = False
        
        return primeira_pagina, is_spread
    except Exception as e:
        # Se o elemento de página não for encontrado, consideramos o fim do encarte ou erro.
        raise Exception(f"Não foi possível determinar o número da página/tipo. Detalhe: {e}")

def cortar_e_salvar_screenshot(pasta_destino: Path, nome_base: str, crop_settings):
    try:
        png = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(png))

        for crop in crop_settings:
            w, h, x, y, suffix = crop["width"], crop["height"], crop["x"], crop["y"], crop["suffix"]

            # 1. Aplica o corte (crop)
            caixa_corte = (x, y, x + w, y + h)
            img_cortada = img.crop(caixa_corte)
            
            # 2. Redimensiona em 2x (aumenta a resolução)
            new_w = w * RESIZE_FACTOR
            new_h = h * RESIZE_FACTOR
            
            try:
                img_redimensionada = img_cortada.resize((new_w, new_h), Image.Resampling.LANCZOS)
            except AttributeError:
                img_redimensionada = img_cortada.resize((new_w, new_h), Image.LANCZOS)
                
            # 3. Salva a imagem redimensionada
            nome_arquivo = f"{nome_base}{suffix}_2x.png"
            arq_saida = pasta_destino / nome_arquivo
            pasta_destino.mkdir(parents=True, exist_ok=True)
            img_redimensionada.save(str(arq_saida))
            print(f" Screenshot recortado e REDIMENSIONADO 2X salvo: {arq_saida} (Final: {new_w}x{new_h})")

    except Exception as e:
        print(f"Erro ao cortar, redimensionar e salvar o screenshot: {e}")


def processar_encartes():
    global driver, wait
    driver = iniciar_driver()
    wait = WebDriverWait(driver, 35)
    driver.get(BASE_URL)
    time.sleep(7)

    # 1. Encontra todos os encartes
    encartes = driver.find_elements(
        By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]'
    )
    total = len(encartes)
    print(f"{total} encarte(s) encontrado(s).")

    for i in range(total):
        try:
            print(f"\nProcessando encarte {i + 1} de {total}")

            driver.get(BASE_URL)
            time.sleep(7)
            encartes = driver.find_elements(
                By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]'
            )

            # Clica no encarte para abrir o visualizador
            encartes[i].click()
            time.sleep(7)

            nome_pasta = f"encarte_{i+1}"
            pasta_encarte = ENCARTE_DIR / nome_pasta
            
            while True:
                try:
                    # 1. LÊ O NÚMERO DA PÁGINA ANTES DO AVANÇO
                    page_number_before_click, is_spread = obter_numero_e_tipo_pagina(wait)

                    # 2. SELECIONA O RECORTE
                    if is_spread:
                        recortes_atuais = CROP_SPREAD_UNICO
                        print(f"  Capturando Páginas {page_number_before_click}-{page_number_before_click+1} (Recorte Spread)...")
                    else:
                        recortes_atuais = CROP_PADRAO
                        print(f"  Capturando Página {page_number_before_click} (Recorte Padrão)...")
                    
                    # 3. Salva o screenshot com corte e 2x upscaling
                    nome_base = f"{nome_pasta}_pag{page_number_before_click}"
                    cortar_e_salvar_screenshot(pasta_encarte, nome_base, recortes_atuais)

                    # 4. Tenta AVANÇAR
                    btn_proximo = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//span[contains(@class, 'flipbook-right-arrow')]")
                        )
                    )
                    
                    # Tenta clicar no botão de próximo
                    btn_proximo.click()
                    time.sleep(5) # Espera a nova página carregar

                    # 5. LÊ O NÚMERO DA PÁGINA DEPOIS DO AVANÇO
                    # Usamos um try/except interno para lidar com a possibilidade de o elemento sumir
                    try:
                        page_number_after_click, _ = obter_numero_e_tipo_pagina(wait)
                    except:
                        # Se não conseguir ler a página depois do clique, assumimos que terminou.
                        print("  Elemento de página não encontrado após clique. Fim do encarte.")
                        break

                    # 6. VERIFICA SE O AVANÇO OCORREU
                    if page_number_after_click <= page_number_before_click:
                        print(f"  Página não avançou ({page_number_after_click} <= {page_number_before_click}). Fim do encarte {i+1}.")
                        break # Sai do loop while e passa para o próximo encarte

                except Exception as e:
                    # Este catch lida com a falha na localização do botão ou falha de conexão.
                    # Se o botão 'próximo' não for encontrado, é o fim do encarte.
                    print(f"  Finalizado o encarte {i+1}. Fim do documento. (Detalhe: {e})")
                    break # Sai do loop while

            print(f"Encarte {i+1} finalizado.")

        except Exception as e:
            print(f"Erro crítico ao processar encarte {i + 1}: {e}")

    driver.quit()
    print("\nTodos os encartes foram processados.")

if __name__ == "__main__":
    try:
        processar_encartes()
    finally:
        # Garante que o driver feche mesmo em caso de erro na inicialização
        if 'driver' in locals() or 'driver' in globals():
            try:
                driver.quit()
            except:
                pass