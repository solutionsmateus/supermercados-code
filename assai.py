import os
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re
from selenium.common.exceptions import TimeoutException, NoSuchElementException

LOJAS_ESTADOS = {
    "Maranhão": "Assaí Angelim",
    "Alagoas": "Assaí Maceió Farol",
    "Ceará": "Assaí Bezerra M (Fortaleza)",
    "Pará": "Assaí Belém",
    "Paraíba": "Assaí João Pessoa Geisel",
    "Pernambuco": "Assaí Avenida Recife",
    "Piauí": "Assaí Teresina",
    "Sergipe": "Assaí Aracaju",
    "Bahia": "Assaí Vitória da Conquista",
}

REGIAO_POR_ESTADO = {
    "Bahia": "Interior",
}

BASE_URL = "https://www.assai.com.br/ofertas"

# Define o diretório de saída para os prints
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/github/workspace/encartes"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--lang=pt-BR,pt")
    return webdriver.Chrome(options=options)

try:
    driver = build_headless_chrome()
except Exception as e:
    print(f"Erro ao inicializar Chrome: {e}")
    exit(1)

wait = WebDriverWait(driver, 30)

def encontrar_data():
    """Tenta encontrar e formatar a data de validade dos encartes."""
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
        for div in enc_data:
            texto = div.text.strip()
            if texto:
                return re.sub(r'[\\/*?:"<>|\s]', '_', texto)
    except:
        pass
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    """Aguarda um elemento estar presente no DOM."""
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR, timeout=30):
    """Aguarda um elemento ser clicável e o clica via JavaScript."""
    element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", element)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", element)

def select_by_visible_text_contains(select_el, target_text):
    """Seleciona uma opção em um <select> cujo texto visível contenha o texto alvo."""
    sel = Select(select_el)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    alvo = target_text.strip().lower()
    for o in opts:
        if alvo in o.text.strip().lower():
            sel.select_by_visible_text(o.text)
            return True
    return False

def tirar_print_encartes(jornal_num, save_dir, loja_nome):
    """
    Navega pelo carrossel de encartes e tira uma captura de tela
    da div do encarte visível a cada página.
    """
    page_num = 1
    
    # Seletor para a div do encarte visível
    ENVELOPE_SELETOR = "div.ofertas-slider"
    ENCARTE_VISIVEL_SELETOR = "div.slick-slide.slick-current.slick-active"

    try:
        envelope_el = aguardar_elemento(ENVELOPE_SELETOR, timeout=30)
    except TimeoutException:
        print("  [ERRO] Não foi possível encontrar o carrossel de ofertas.")
        return

    while True:
        print(f"  Tirando print da página {page_num} do jornal {jornal_num}...")
        
        # 1. Encontra o elemento específico (div) do encarte ativo
        try:
            encarte_el = envelope_el.find_element(By.CSS_SELECTOR, ENCARTE_VISIVEL_SELETOR)
        except NoSuchElementException:
            print("  [FIM] Não foi possível encontrar o slide ativo. Fim do carrossel.")
            break

        # Rola o elemento para o centro da tela antes de tirar a print para garantir a visibilidade
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", encarte_el)
        time.sleep(1) # Tempo para a rolagem e renderização final

        # 2. Tira o print do elemento
        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        filename = f"{loja_nome}_jornal_{jornal_num}_pagina_{page_num}_{ts}.png"
        path = save_dir / filename
        
        try:
            # Captura de tela focada no elemento
            encarte_el.screenshot(str(path))
            print(f"    [PRINT] {path.name} salvo.")
        except Exception as e:
            print(f"    [ERRO] Falha ao tirar print da página {page_num}: {e}")
            
        # 3. Tenta ir para o próximo slide
        try:
            # O botão next fica FORA da div do slide
            next_btn = driver.find_element(By.CSS_SELECTOR, "button.slick-next:not(.slick-disabled)")
            
            # Garante que o botão está visível/clicável
            driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", next_btn)
            time.sleep(0.5)
            
            # Clica no botão para o próximo encarte
            driver.execute_script("arguments[0].click();", next_btn)

            # Aguarda a transição para o próximo slide
            time.sleep(2.5) 
            page_num += 1

        except NoSuchElementException:
            print("  [FIM] Botão Next desabilitado ou não encontrado. Fim do carrossel.")
            break
        except Exception as e:
            print(f"  [FIM] Erro ao avançar o carrossel: {e}")
            break
    
try:
    driver.get(BASE_URL)
    time.sleep(3)

    try:
        # Tenta fechar o pop-up de cookies, se houver
        clicar_elemento("button.ot-close-icon", timeout=5)
    except:
        pass

    # Clica no seletor de loja
    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        # Define o nome da loja seguro para o diretório
        nome_loja = re.sub(r'[\\/*?:"<>|\s]', '_', loja)
        
        print(f"\n--- Processando: {estado} - {loja} ---")

        # 1. Seleção de Estado
        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # 2. Seleção de Região (se aplicável)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f"  Região não selecionada: {e}")

        # 3. Seleção de Loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            if not select_by_visible_text_contains(loja_select, loja):
                raise RuntimeError(f"Loja não encontrada: {loja}")

        time.sleep(0.8)

        # 4. Confirmação
        clicar_elemento("button.confirmar")
        time.sleep(3)

        # 5. Define diretório de saída e nome da data
        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()
        
        # Cria a pasta de saída baseada na loja e na data
        download_dir = OUTPUT_DIR / f"encartes_{nome_loja}_{data_nome}"
        download_dir.mkdir(parents=True, exist_ok=True)

        # 6. Processa o primeiro jornal (padrão)
        tirar_print_encartes(1, download_dir, nome_loja)

        # 7. Processa outros jornais (se houver botões)
        for i in range(2, 4):
            try:
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                tirar_print_encartes(i, download_dir, nome_loja)
            except Exception as e:
                print(f"  Jornal {i} não disponível: {e}")

        # 8. Retorna para o seletor de loja para o próximo loop
        try:
            clicar_elemento("a.seletor-loja")
            time.sleep(2)
        except:
            pass

    print("\nTodos os encartes foram processados!")

except Exception as e:
    print(f"\nERRO CRÍTICO: {e}")
    try:
        # Tira screenshot da tela inteira em caso de erro crítico
        screenshot_path = OUTPUT_DIR / "ERRO_assai_tela_cheia.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"  Screenshot de erro salvo: {screenshot_path}")
    except:
        pass
finally:
    driver.quit()