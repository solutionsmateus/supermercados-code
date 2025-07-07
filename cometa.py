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
    options.add_argument("--headless=new")  
    return webdriver.Chrome(options=options)

def salvar_print(driver, pasta_destino, nome_arquivo):
    caminho = pasta_destino / nome_arquivo
    driver.save_screenshot(str(caminho))
    print(f"📸 Print salvo: {nome_arquivo}")

def processar_encartes():
    driver = iniciar_driver()
    wait = WebDriverWait(driver, 15)
    driver.get(BASE_URL)
    time.sleep(3)

    encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]')
    total = len(encartes)
    print(f"🧾 {total} encarte(s) encontrado(s).")

    for i in range(total):
        try:
            print(f"\n➡️ Processando encarte {i + 1} de {total}")

            driver.get(BASE_URL)
            time.sleep(3)
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]')

            encartes[i].click()
            time.sleep(5)

            nome_pasta = f"encarte_{i+1}"
            pasta_encarte = ENCARTE_DIR / nome_pasta
            pasta_encarte.mkdir(parents=True, exist_ok=True)

            pagina = 1
            while True:
                nome_arquivo = f"{nome_pasta}_pagina_{pagina}.png"
                salvar_print(driver, pasta_encarte, nome_arquivo)

                try:
                    btn_proximo = driver.find_element(By.CLASS_NAME, "flipbook-right-arrow")
                    if not btn_proximo.is_displayed():
                        break
                    btn_proximo.click()
                    time.sleep(2)
                    pagina += 1
                except:
                    break

        except Exception as e:
            print(f"❌ Erro ao processar encarte {i + 1}: {e}")

    driver.quit()
    print("\n✅ Todos os encartes foram processados.")

processar_encartes()
