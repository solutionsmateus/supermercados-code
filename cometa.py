import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://cometasupermercados.com.br/ofertas/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/Cometa-Supermercados"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)

# === CHROME HEADLESS ===
def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")              # headless moderno
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")     # substitui start-maximized no headless
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

def salvar_print(driver, pasta_destino, nome_arquivo):
    # garante topo da página para screenshots consistentes
    driver.execute_script("window.scrollTo(0, 0);")
    caminho = pasta_destino / nome_arquivo
    driver.save_screenshot(str(caminho))
    print(f" Print salvo: {nome_arquivo}")

def processar_encartes():
    driver = iniciar_driver()
    wait = WebDriverWait(driver, 35)
    driver.get(BASE_URL)
    time.sleep(10)

    encartes = driver.find_elements(
        By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]'
    )
    total = len(encartes)
    print(f" {total} encarte(s) encontrado(s).")

    for i in range(total):
        try:
            print(f"\n Processando encarte {i + 1} de {total}")

            driver.get(BASE_URL)
            time.sleep(9)
            encartes = driver.find_elements(
                By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]'
            )

            encartes[i].click()
            time.sleep(9)

            nome_pasta = f"encarte_{i+1}"
            pasta_encarte = ENCARTE_DIR / nome_pasta
            pasta_encarte.mkdir(parents=True, exist_ok=True)

            pagina = 1
            max_paginas = 20  # Limite máximo para evitar loops infinitos
            paginas_salvas = set()  # Rastreia páginas já salvas
            
            while pagina <= max_paginas:
                try:
                    # Identificador único da página atual (se existir)
                    try:
                        page_indicator = driver.find_element(
                            By.XPATH, "//div[contains(@class, 'flipbook-page')]"
                        ).get_attribute('data-page')
                        if page_indicator in paginas_salvas:
                            print(f"  Página {page_indicator} já foi salva. Finalizando encarte {i+1}.")
                            break
                        paginas_salvas.add(page_indicator)
                    except:
                        if pagina in paginas_salvas:
                            print(f"  Página {pagina} já foi salva. Finalizando encarte {i+1}.")
                            break
                        paginas_salvas.add(pagina)
                    
                    nome_arquivo = f"{nome_pasta}_pagina_{pagina}.png"
                    salvar_print(driver, pasta_encarte, nome_arquivo)
                    
                    # Próxima página
                    try:
                        btn_proximo = wait.until(
                            EC.element_to_be_clickable(
                                (By.XPATH, "//span[contains(@class, 'flipbook-right-arrow')]")
                            )
                        )
                        if btn_proximo.is_enabled() and btn_proximo.is_displayed():
                            btn_proximo.click()
                            time.sleep(6)
                            pagina += 1
                        else:
                            print(f"Botão próximo não está habilitado. Finalizando encarte {i+1}.")
                            break
                    except Exception:
                        print(f"Não foi possível encontrar o botão próximo. Finalizando encarte {i+1}.")
                        break
                        
                except Exception as e:
                    print(f"Erro ao processar página {pagina} do encarte {i+1}: {e}")
                    break

            print(f"Encarte {i+1} finalizado com {len(paginas_salvas)} páginas.")

        except Exception as e:
            print(f" Erro ao processar encarte {i + 1}: {e}")

    driver.quit()
    print("\nTodos os encartes foram processados.")

processar_encartes()
