import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://novoatacarejo.com/oferta/"
ENCARTE_DIR = Path.home() / "Desktop/Encartes-Concorrentes"


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
    #"h6 - TEXT LOCATION OF DATES IN PAGE"
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//h6[contains(\"TEXT\")]"))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def selecionar_loja():
    driver.get(BASE_URL)
    select_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "select.select")))
    select = Select(select_element)
    select.select_by_visible_text("Olinda")
    time.sleep(4)  

def clicar_nas_imagens():
    imagens = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tabloids a")))

    for i in range(min(2, len(imagens))):
        link = imagens[i].get_attribute("href")
        # Corrected line: Pass link as an argument to JavaScript
        driver.execute_script("window.open(arguments[0], arguments[1]);", link, "_blank")
        time.sleep(1)  

   
    abas = driver.window_handles
    
    for i in range(1, min(3, len(abas))):
        driver.switch_to.window(abas[i])
        time.sleep(5)
        
        # Take screenshot when transitioning to a new leaflet
        driver.save_screenshot(str(ENCARTE_DIR))
        print(f" Screenshot do encarte {i} salvo em: {ENCARTE_DIR}")

        screenshot_path = ENCARTE_DIR / f"Ofertas Novo Atacarejo{i}_pag1.png"
        driver.save_screenshot(str(screenshot_path))
        time.sleep(2)
        
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "div.pdff-ui-btn.pdff-ui-next.pdff-ui-alt.fa.fa-chevron-right[title=\'Next Page\']")
            next_button.click()
            time.sleep(5) 
            
            screenshot_path_2 = ENCARTE_DIR / f"Ofertas Novo Atacarejo{i}_pag2.png"
            driver.save_screenshot(str(screenshot_path_2))
        except Exception as e:
            print(f"Erro ao clicar ou capturar a página 2 da aba {i}: {e}")


selecionar_loja()
clicar_nas_imagens()

driver.quit()