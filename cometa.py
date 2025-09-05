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

def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)

def salvar_print(driver, pasta_destino, nome_arquivo):
    caminho = pasta_destino / nome_arquivo
    driver.save_screenshot(str(caminho))
    print(f" Print salvo: {nome_arquivo}")

def processar_encartes():
    driver = iniciar_driver()
    wait = WebDriverWait(driver, 35)
    driver.get(BASE_URL)
    time.sleep(10)

    encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]')
    total = len(encartes)
    print(f" {total} encarte(s) encontrado(s).")

    for i in range(total):
        try:
            print(f"\n Processando encarte {i + 1} de {total}")

            driver.get(BASE_URL)
            time.sleep(9)
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]')

            encartes[i].click()
            time.sleep(9)

            nome_pasta = f"encarte_{i+1}"
            pasta_encarte = ENCARTE_DIR / nome_pasta
            pasta_encarte.mkdir(parents=True, exist_ok=True)

            pagina = 1
            max_paginas = 20  # Limite máximo de páginas para evitar loops infinitos
            paginas_salvas = set()  # Para rastrear páginas já salvas
            
            while pagina <= max_paginas:
                try:
                    # Captura um identificador único da página atual (pode ser o URL ou algum elemento específico)
                    try:
                        # Tenta encontrar um indicador de página atual
                        page_indicator = driver.find_element(By.XPATH, "//div[contains(@class, 'flipbook-page')]").get_attribute('data-page')
                        if page_indicator in paginas_salvas:
                            print(f"  Página {page_indicator} já foi salva. Finalizando encarte {i+1}.")
                            break
                        paginas_salvas.add(page_indicator)
                    except:
                        # Se não conseguir encontrar o indicador, usa o número da página
                        if pagina in paginas_salvas:
                            print(f"  Página {pagina} já foi salva. Finalizando encarte {i+1}.")
                            break
                        paginas_salvas.add(pagina)
                    
                    nome_arquivo = f"{nome_pasta}_pagina_{pagina}.png"
                    salvar_print(driver, pasta_encarte, nome_arquivo)
                    
                    # Tenta encontrar e clicar no botão próximo
                    try:
                        btn_proximo = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'flipbook-right-arrow')]"))
                        )
                        # Verifica se o botão está habilitado/visível
                        if btn_proximo.is_enabled() and btn_proximo.is_displayed():
                            btn_proximo.click()
                            time.sleep(6)
                            pagina += 1
                        else:
                            print(f"Botão próximo não está habilitado. Finalizando encarte {i+1}.")
                            break
                    except Exception as e:
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
