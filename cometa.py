import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://cometasupermercados.com.br/ofertas/"

# === SAÍDA PADRONIZADA (usa env OUTPUT_DIR; fallback ./Encartes/Cometa-Supermercados) ===
BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = (BASE_OUTPUT / "Cometa-Supermercados")
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[cometa.py] Pasta base de saída: {ENCARTE_DIR}")

# === CHROME HEADLESS ===
def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")              # headless moderno
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")     # viewport consistente
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

def salvar_print(driver, pasta_destino: Path, nome_arquivo: str):
    driver.execute_script("window.scrollTo(0, 0);")  # garante topo
    caminho = pasta_destino / nome_arquivo
    pasta_destino.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(caminho))
    print(f"  Print salvo: {caminho}")

def processar_encartes():
    driver = iniciar_driver()
    wait = WebDriverWait(driver, 35)
    driver.get(BASE_URL)
    time.sleep(10)

    encartes = driver.find_elements(
        By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]'
    )
    total = len(encartes)
    print(f"{total} encarte(s) encontrado(s).")

    for i in range(total):
        try:
            print(f"\nProcessando encarte {i + 1} de {total}")

            # Recarrega a listagem antes de clicar (evita stale element)
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
            print(f"Pasta do encarte: {pasta_encarte}")

            pagina = 1
            max_paginas = 20  # limite de segurança
            paginas_salvas = set()

            while pagina <= max_paginas:
                try:
                    # Tenta identificar a página exibida (se houver data-page no DOM)
                    page_id = None
                    try:
                        page_id = driver.find_element(
                            By.XPATH, "//div[contains(@class, 'flipbook-page')]"
                        ).get_attribute('data-page')
                    except:
                        pass

                    chave_unica = page_id if page_id else str(pagina)
                    if chave_unica in paginas_salvas:
                        print(f"  Página {chave_unica} já salva. Encerrando encarte {i+1}.")
                        break
                    paginas_salvas.add(chave_unica)

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
                            print(f"  Botão 'próximo' não habilitado. Finalizando encarte {i+1}.")
                            break
                    except Exception:
                        print(f"  Não foi possível encontrar o botão 'próximo'. Finalizando encarte {i+1}.")
                        break

                except Exception as e:
                    print(f"  Erro ao processar página {pagina} do encarte {i+1}: {e}")
                    break

            print(f"Encarte {i+1} finalizado com {len(paginas_salvas)} página(s).")

        except Exception as e:
            print(f"Erro ao processar encarte {i + 1}: {e}")

    driver.quit()
    print("\nTodos os encartes foram processados.")

if __name__ == "__main__":
    processar_encartes()
