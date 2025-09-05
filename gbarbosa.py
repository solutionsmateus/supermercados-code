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

sigla_estado = {
    "AL",
    "SE"
}

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)


def baixar_estado(sigla_estado):
    print(f"\n Baixando encartes do estado: {sigla_estado}")
    driver.get(BASE_URL)
    time.sleep(5)

    try:
        botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
        botao_estado.click()
        time.sleep(5)
    except Exception as e:
        print(f"Erro ao selecionar o estado {sigla_estado}: {e}")
        return

    index = 1
    while True:
        try:
            encartes = driver.find_elements(By.XPATH, '//div[contains(@class, "df-book-cover")]')
            if index >= len(encartes):
                break

            print(f"\n Abrindo encarte {index+1}...")
            encartes[index].click()
            time.sleep(2)

            menu_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[contains(@class, "df-ui-btn df-ui-more")]')))
            menu_btn.click()
            time.sleep(2)

            download_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//a[contains(@class, "df-ui-download")]')))
            download_btn.click()
            print(" Download iniciado.")
            time.sleep(5)

            driver.get(BASE_URL)
            time.sleep(5)

            botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
            botao_estado.click()
            time.sleep(5)

            index += 1

        except Exception as e:
            print(f" Erro no encarte {index+1}: {e}")
            driver.get(BASE_URL)
            time.sleep(5)
            try:
                botao_estado = wait.until(EC.element_to_be_clickable((By.XPATH, f'//button[text()="{sigla_estado}"]')))
                botao_estado.click()
                time.sleep(5)
            except:
                break
            index += 1
            continue

baixar_estado("AL")
baixar_estado("SE")

driver.quit()
