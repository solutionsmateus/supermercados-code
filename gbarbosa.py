import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://blog.gbarbosa.com.br/ofertas/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes/G-Barbosa"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
prefs = {
    "download.prompt_for_download": False,
    "download.default_directory": str(ENCARTE_DIR),
    "directory_upgrade": True,
    "safebrowsing.enabled": True
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

def encontrar_data():
    
    #P LOCALED DATA"
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//p[contains("TEXT")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def baixar_estado(sigla_estado):
    print(f"\n Baixando encartes do estado: {sigla_estado}")
    driver.get(BASE_URL)
    time.sleep(3)

    try:
        botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
        botao_estado.click()
        time.sleep(2)
    except Exception as e:
        print(f"Erro ao selecionar o estado {sigla_estado}: {e}")
        return

    encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')

    for i in range(len(encartes)):
        try:
            print(f"\n Abrindo encarte {i+1}...")
            encartes[i].click()
            time.sleep(2)

            menu_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[contains(@class, "df-ui-btn df-ui-more")]')))
            menu_btn.click()
            time.sleep(2)

            download_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//a[contains(@class, "df-ui-download")]')))
            download_btn.click()
            print("⬇️ Download iniciado.")
            time.sleep(2)

            driver.get(BASE_URL)
            time.sleep(3)


            botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
            botao_estado.click()
            time.sleep(3)

    
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')

        except Exception as e:
            print(f" Erro no encarte {i+1}: {e}")
            driver.get(BASE_URL)
            time.sleep(3)
            try:
                botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
                botao_estado.click()
                time.sleep(3)
                encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')
            except:
                continue
            continue

baixar_estado("AL")
baixar_estado("SE")

driver.quit()
