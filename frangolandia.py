import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


options = webdriver.ChromeOptions()
prefs = {
    "download.prompt_for_download": False,
    "plugins.always_open_pdf_externally": True
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

BASE_URL = "https://frangolandia.com/encartes/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/Frangolandia"
os.makedirs(ENCARTE_DIR, exist_ok=True)

def encontrar_data():
    #span - elementor-button-text"
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(By.XPATH, '//span[contains(@class, "elementor-button-text")]')
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def coleta_encartes():
    driver.get(BASE_URL)
    time.sleep(3)
    encartes = driver.find_elements(By.CSS_SELECTOR, "a.jet-engine-listing-overlay-link")
    links = [e.get_attribute("href") for e in encartes if e.get_attribute("href")]
    return links

def processar_encartes(links): 
    for url in links:
        try:
            driver.get(url)
            print(f"\n Acessando: {url}")
            time.sleep(3)
            
            
            galeria_itens = driver.find_elements(By.CSS_SELECTOR, "a.e-gallery-item.elementor-gallery-item.elementor-animated-content")
            for item in galeria_itens:
                try:
                    item.click()
                    time.sleep(1)
                except Exception as click_err:
                    print(f" Falha ao clicar no item da galeria: {click_err}")

            imagens = driver.find_elements(By.CSS_SELECTOR, "img[src*='uploads/2025/']")
            if not imagens:
                print(" Nenhuma imagem de encarte encontrada.")
                continue

            for i, img in enumerate(imagens):
                src = img.get_attribute("src")
                nome_base = url.strip('/').split('/')[-1]
                nome_arquivo = f"{ENCARTE_DIR}/{nome_base}_{i+1}.jpg"

                try:
                    response = requests.get(src)
                    if response.status_code == 200:
                        with open(nome_arquivo, 'wb') as f:
                            f.write(response.content)
                        print(f" Imagem baixada: {nome_arquivo}")
                    else:
                        raise Exception("Download falhou")
                except Exception:

                    try:
                        img.screenshot(nome_arquivo)
                        print(f"Screenshot salva: {nome_arquivo}")
                    except Exception as screenshot_err:
                        print(f" Falha ao salvar imagem: {screenshot_err}")

        except Exception as e:
            print(f" Erro ao processar {url}: {e}")

try:
    links = coleta_encartes()
    processar_encartes(links)
    print("\n Processo finalizado.")
except Exception as e:
    print(f" Erro geral: {e}")
finally:
    driver.quit()
