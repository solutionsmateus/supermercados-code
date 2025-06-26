import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC



BASE_URL = "https://cometasupermercados.com.br/ofertas/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/Cometa-Supermercados"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
driver = webdriver

def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)

#LOCATED of div//jet-listing-dynamic-field__content

def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "jet-listing-dynamic-field__content")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def baixar_arquivo(url, caminho):
    try:
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            with open(caminho, "wb") as f:
                f.write(resposta.content)
            print(f" Imagem salva: {caminho.name}")
        else:
            print(f" Falha ao baixar {url}")
    except Exception as e:
        print(f" Erro ao baixar imagem: {e}")

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
            print(f"\n Processando encarte {i + 1} de {total}")
            driver.get(BASE_URL)
            time.sleep(2)

            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "real3dflipbook") and contains(@style, "cursor: pointer")]')
            encartes[i].click()
            time.sleep(5)

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='./Ofertas Cometa Supermercados_files/']")))
            imagens = driver.find_elements(By.CSS_SELECTOR, "img[src*='./Ofertas Cometa Supermercados_files/']")

            if not imagens:
                print("Nenhuma imagem encontrada.")
                continue

            for j, img in enumerate(imagens):
                src = img.get_attribute("src")
                if src:
                    nome = f"encarte_{i+1}_pagina_{j+1}.jpg"
                    caminho = ENCARTE_DIR / nome
                    baixar_arquivo(src, caminho)

        except Exception as e:
            print(f"Erro ao processar encarte {i + 1}: {e}")

    driver.quit()
    print("\nTodos os encartes foram processados.")


processar_encartes()
