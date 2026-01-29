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


LOJAS_PARA_PROCESSAR = [
    # Maranhão
    {"estado": "Maranhão", "loja": "Assaí Angelim", "regiao": None},
    # Alagoas
    {"estado": "Alagoas", "loja": "Assaí Maceió Farol", "regiao": None},
    # Ceará
    {"estado": "Ceará", "loja": "Assaí Bezerra M (Fortaleza)", "regiao": None},
    # Pará
    {"estado": "Pará", "loja": "Assaí Belém", "regiao": None},
    # Paraíba
    {"estado": "Paraíba", "loja": "Assaí João Pessoa Geisel", "regiao": None},
    # Pernambuco
    {"estado": "Pernambuco", "loja": "Assaí Avenida Recife", "regiao": None},
    # Piauí
    {"estado": "Piauí", "loja": "Assaí Teresina", "regiao": None},
    # Sergipe
    {"estado": "Sergipe", "loja": "Assaí Aracaju", "regiao": None},
    
    # BAHIA - Interior
    {"estado": "Bahia", "loja": "Assaí Vitória da Conquista", "regiao": "Interior"},
    
    # BAHIA - Capital (Adicionada Salvador Paralela)
    {"estado": "Bahia", "loja": "Salvador Paralela", "regiao": "Capital"},
]

BASE_URL = "https://www.assai.com.br/ofertas"

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/github/workspace/encartes"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[assai.py] Pasta de saída: {OUTPUT_DIR}")

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
    time.sleep(1)
    element.click()

def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(1)

def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()
    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
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
                # Usa a página do jornal e o índice da página atual para nomear o arquivo
                file_path = download_dir / f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{int(time.time())}.jpg"
                with open(file_path, "wb") as f:
                    f.write(response.content)
                print(f"  Encarte {file_path.name} salvo.")
            else:
                print(f"Falha no download: {url} (Status: {response.status_code})")

        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(1)
            next_button.click()
            time.sleep(2)
            page_num += 1
        except:
            break

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

# --- Lógica Principal (Ajustada para iterar sobre a nova lista) ---
try:
    driver.get(BASE_URL)
    time.sleep(2)

    try:
        clicar_elemento("button.ot-close-icon")
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    # Iterar sobre a nova lista de dicionários
    for item in LOJAS_PARA_PROCESSAR:
        estado = item["estado"]
        loja = item["loja"]
        regiao = item["regiao"]
        
        print(f"\n--- Processando: {estado} - {loja} (Região: {regiao or 'N/A'}) ---")

        # 1. Selecionar Estado
        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # 2. Selecionar Região (se aplicável)
        if regiao:
            try:
                # O seletor de região deve aparecer se o estado o exigir (ex: Bahia)
                regiao_select_element = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select_element).select_by_visible_text(regiao)
                # Espera as lojas da região carregarem
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                # Loga o erro, mas continua, caso a região não seja realmente um select
                print(f" Não foi possível selecionar a região '{regiao}' para {estado}. Tentando continuar...")

        # 3. Selecionar Loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        # Tenta seleção exata; se falhar, usa "contains" (mais robusto)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            ok = select_by_visible_text_contains(loja_select, loja)
            if not ok:
                raise RuntimeError(f"Não encontrei a loja '{loja}' no estado {estado}")

        time.sleep(0.8)

        # 4. Confirmar Seleção
        clicar_elemento("button.confirmar")
        time.sleep(1)

        # 5. Processar Encartes
        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()

        nome_loja = loja.replace(' ', '_').replace('(', '').replace(')', '')
        download_dir = OUTPUT_DIR / f"encartes_{nome_loja}_{data_nome}"
        os.makedirs(download_dir, exist_ok=True)

        # Baixa o primeiro jornal
        scroll_down_and_up()
        baixar_encartes(1, download_dir)

        # Baixa os jornais subsequentes
        for i in range(2, 6):
            try:
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                scroll_down_and_up()
                baixar_encartes(i, download_dir)
            except Exception as e:
                print(f" Jornal {i} indisponível para {loja}. Tentando próximo.")
        
        # 6. Voltar para o Seletor de Loja para a próxima iteração
        clicar_elemento("a.seletor-loja")
        time.sleep(2)

    print("\nTodos os encartes foram processados!")

except Exception as e:
    print(f"\nErro crítico: {str(e)}")
    driver.save_screenshot(str(OUTPUT_DIR / "erro_encartes.png"))

finally:
    driver.quit()