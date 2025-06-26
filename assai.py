import os
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import re
import sys
import json # Importar json para saída formatada

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

LOJAS_ESTADOS = {
    "Maranhão": "Assaí Angelim",
    "Alagoas": "Assaí Maceió Farol",
    "Ceará": "Assaí Bezerra M (Fortaleza)",
    "Pará": "Assaí Belém",
    "Paraíba": "Assaí João Pessoa Geisel",
    "Pernambuco": "Assaí Avenida Recife",
    "Piauí": "Assaí Teresina",
    "Sergipe": "Assaí Aracaju",
    "Bahia": "Interior Vitória da Conquista",
}

BASE_URL = "https://www.assai.com.br/ofertas"

download_base_path = Path("downloads/Assai")
os.makedirs(download_base_path, exist_ok=True)

driver = None
wait = None

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
    return wait.until(EC.presence_of_element_located((by, seletor)))

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

# FUNÇÃO baixar_encartes CORRIGIDA
def baixar_encartes(jornal_num, download_dir):
    baixados = []
    try: # Adicionado um try-except para o WebDriverWait também
        links_download = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@class, 'download') and contains(@href, '.jpeg')]")
            )
        )
    except Exception as e:
        print(f"Não foram encontrados links de download para o jornal {jornal_num}: {e}")
        return baixados # Retorna lista vazia se não encontrar links

    for idx, link in enumerate(links_download, start=1):
        url = link.get_attribute("href")
        if url:
            try:
                response = requests.get(url, stream=True) # Use stream=True para arquivos grandes
                response.raise_for_status() # Lança um erro para status de erro HTTP

                file_name = f"encarte_jornal_{jornal_num}_{idx}_{int(time.time())}.jpg"
                file_path = download_dir / file_name
                
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192): # Baixa em pedaços
                        f.write(chunk)
                print(f" Encarte {file_path.name} salvo.")
                baixados.append(str(file_path.resolve())) # Guarda o caminho ABSOLUTO para maior clareza para o app.py
            except requests.exceptions.RequestException as e:
                print(f" Falha no download de {url}: {e}")
            except Exception as e:
                print(f" Erro inesperado ao salvar {url}: {e}")
    return baixados # <--- AGORA ESTÁ FORA DO LOOP!

def main():
    global driver, wait
    all_downloaded_files = [] # Lista para coletar todos os caminhos dos arquivos baixados

    driver = get_chrome_driver()
    wait = WebDriverWait(driver, 30)

    loja_param = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Executando script para a loja: {loja_param}")

    try:
        driver.get(BASE_URL)
        time.sleep(2)

        try:
            clicar_elemento("button.ot-close-icon")
        except:
            pass

        clicar_elemento("a.seletor-loja")
        time.sleep(1)

        lojas_to_process = LOJAS_ESTADOS.items()
        if loja_param and loja_param in LOJAS_ESTADOS.values():
            found_state = None
            for state, store_name in LOJAS_ESTADOS.items():
                if store_name == loja_param:
                    found_state = state
                    break
            if found_state:
                lojas_to_process = [(found_state, loja_param)]
            else:
                print(f"Loja '{loja_param}' não encontrada nos mapeamentos. Processando todas.")

        for estado, loja in lojas_to_process:
            print(f"➡️ Processando: {estado} - {loja}")
            estado_select = aguardar_elemento("select.estado")
            Select(estado_select).select_by_visible_text(estado)
            time.sleep(1)
            aguardar_elemento("select.loja option[value]", timeout=20)
            loja_select = aguardar_elemento("select.loja")
            Select(loja_select).select_by_visible_text(loja)
            time.sleep(1)
            clicar_elemento("button.confirmar")
            time.sleep(3)
            aguardar_elemento("div.ofertas-slider", timeout=30)
            data_nome = encontrar_data()
            nome_loja = loja.replace(' ', '_').replace('(', '').replace(')', '')
            download_dir = download_base_path / f"encartes_{nome_loja}_{data_nome}"
            os.makedirs(download_dir, exist_ok=True)
            print(f"Salvando encartes em: {download_dir.resolve()}")
            scroll_down_and_up()
            
            # Chama baixar_encartes e estende a lista global de arquivos baixados
            baixados_jornal_1 = baixar_encartes(1, download_dir)
            all_downloaded_files.extend(baixados_jornal_1)

            for i in range(2, 4):
                try:
                    clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                    time.sleep(3)
                    aguardar_elemento("div.ofertas-slider", timeout=30)
                    scroll_down_and_up()
                    baixados_jornal_i = baixar_encartes(i, download_dir)
                    all_downloaded_files.extend(baixados_jornal_i)
                except Exception as e:
                    print(f" Jornal {i} indisponível para {loja}: {str(e)}")

            clicar_elemento("a.seletor-loja")
            time.sleep(2)

        print("✔️ Todos os encartes foram processados!")

    except Exception as e:
        print(f"❌ Erro crítico: {str(e)}")
        screenshot_path = download_base_path / "erro_encartes.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"Screenshot do erro salvo em: {screenshot_path.resolve()}")

    finally:
        if driver:
            driver.quit()


    print(f"DOWNLOADED_FILES:{json.dumps(all_downloaded_files)}")


if __name__ == "__main__":
    main()