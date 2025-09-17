import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re
import os

# CHANGE: Ajuste do mapeamento da Bahia para o NOME DA LOJA (e não a região)
LOJAS_ESTADOS = {
    "Maranhão": "Assaí Angelim",
    "Alagoas": "Assaí Maceió Farol",
    "Ceará": "Assaí Bezerra M (Fortaleza)",
    "Pará": "Assaí Belém",
    "Paraíba": "Assaí João Pessoa Geisel",
    "Pernambuco": "Assaí Avenida Recife",
    "Piauí": "Assaí Teresina",
    "Sergipe": "Assaí Aracaju",
    "Bahia": "Assaí Vitória da Conquista",  # CHANGE
}

# CHANGE: Região preferida por estado (usado quando existe select.regiao)
REGIAO_POR_ESTADO = {
    "Bahia": "Interior",  # CHANGE: explicitamos a região para BA
}

BASE_URL = "https://www.assai.com.br/ofertas"
desktop_path = Path.home() / "Desktop/Encartes-Concorrentes/Assai"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 30)

def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR):
    element = wait.until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()

def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.5)

def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()
    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        links_download = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@class, 'download') and contains(@href, '.jpeg')]")
            )
        )
        current_page_urls = []
        for link in links_download:
            url = link.get_attribute("href")
            if url and url not in downloaded_urls:
                current_page_urls.append(url)
                downloaded_urls.add(url)

        if not current_page_urls and page_num > 1:
            break

        for idx, url in enumerate(current_page_urls, start=1):
            response = requests.get(url)
            if response.status_code == 200:
                file_path = download_dir / f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{int(time.time())}.jpg"
                with open(file_path, "wb") as f:
                    f.write(response.content)
                print(f"  Encarte {file_path.name} salvo.")
            else:
                print(f"Falha no download: {url} (Status: {response.status_code})")

        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.5)
            next_button.click()
            time.sleep(2)
            page_num += 1
        except:
            break

# CHANGE: helper para selecionar por "contém texto" (robusto contra variações de acento/espaço)
def select_by_visible_text_contains(select_el, target_text, timeout=10):
    WebDriverWait(driver, timeout).until(lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 0)
    sel = Select(select_el)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    alvo_norm = target_text.strip().lower()
    for o in opts:
        if alvo_norm in o.text.strip().lower():
            sel.select_by_visible_text(o.text)
            return True
    return False

try:
    driver.get(BASE_URL)
    time.sleep(2)

    try:
        clicar_elemento("button.ot-close-icon")
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f" Processando: {estado} - {loja}")

        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # CHANGE: se o site exibir seletor de região para o estado, seleciona antes de escolher a loja
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select_element = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select_element).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                # Espera as lojas da região carregarem
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f" Não foi possível selecionar a região para {estado}: {e}")

        # CHANGE: espera corretamente o select.loja (um único elemento) e depois seleciona pelo NOME DA LOJA
        loja_select = aguardar_elemento("select.loja", timeout=20)
        # Tenta seleção exata; se falhar, usa "contains"
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            ok = select_by_visible_text_contains(loja_select, loja)
            if not ok:
                raise RuntimeError(f"Não encontrei a loja '{loja}' no estado {estado}")

        time.sleep(0.8)

        clicar_elemento("button.confirmar")
        time.sleep(1)

        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()

        nome_loja = loja.replace(' ', '_').replace('(', '').replace(')', '')
        download_dir = desktop_path / f"encartes_{nome_loja}_{data_nome}"
        os.makedirs(download_dir, exist_ok=True)

        scroll_down_and_up()
        baixar_encartes(1, download_dir)

        for i in range(2, 4):
            try:
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                scroll_down_and_up()
                baixar_encartes(i, download_dir)
            except Exception as e:
                print(f" Jornal {i} indisponível para {loja}: {str(e)}")

        clicar_elemento("a.seletor-loja")
        time.sleep(2)

    print("Todos os encartes foram processados!")

except Exception as e:
    print(f"Erro crítico: {str(e)}")
    driver.save_screenshot(str(desktop_path / "erro_encartes.png"))

finally:
    driver.quit()
