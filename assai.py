import os
import time
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
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

# Define o diretório de saída
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/github/workspace/encartes"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[assai.py] Pasta de saída: {OUTPUT_DIR}")

def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    # Aumentei um pouco a altura para garantir que o print pegue o encarte todo sem cortes
    options.add_argument("--window-size=1920,1200")
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
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR, timeout=30):
    element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", element)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", element)

def select_by_visible_text_contains(select_el, target_text):
    sel = Select(select_el)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    alvo = target_text.strip().lower()
    for o in opts:
        if alvo in o.text.strip().lower():
            sel.select_by_visible_text(o.text)
            return True
    return False

def baixar_encartes(jornal_num, download_dir):
    """
    Navega pelo carrossel e tira um SCREENSHOT da DIV ativa do encarte.
    """
    page_num = 1
    
    while True:
        print(f"  Processando (Screenshot) página {page_num} do jornal {jornal_num}...")

        # Seletor da DIV container do slide ativo.
        # Esta DIV contém a imagem e a borda/layout que você quer capturar.
        SLIDE_ATIVO_XPATH = "//div[contains(@class, 'slick-slide') and contains(@class, 'slick-active')]"
        
        try:
            # 1. Localiza o elemento DIV ativo
            div_encarte = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, SLIDE_ATIVO_XPATH))
            )
            
            # Pequena pausa para garantir que a imagem dentro da div carregou completamente
            time.sleep(2) 
            
            # Define o nome do arquivo
            filename = f"encarte_j{jornal_num}_pagina_{page_num}.png"
            path = download_dir / filename
            
            # 2. Tira o screenshot APENAS dessa DIV
            div_encarte.screenshot(str(path))
            print(f"    [SCREENSHOT SALVO] {path.name}")

        except TimeoutException:
            if page_num > 1:
                print("  Nenhum slide ativo encontrado. Fim do carrossel.")
                break
            else:
                print("  [ERRO] Não foi possível encontrar o primeiro slide ativo.")
                break
        except Exception as e:
             print(f"    [Erro] Falha ao tirar screenshot: {e}")

        # 3. Tenta ir para o próximo slide
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button.slick-next:not(.slick-disabled)")
            
            if "slick-disabled" in next_btn.get_attribute("class"):
                print("  Botão Next desabilitado. Fim do carrossel.")
                break

            driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", next_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", next_btn)

            # Aguarda o slide atual mudar de índice (lógica para garantir transição)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, f"//div[contains(@class, 'slick-slide') and contains(@class, 'slick-active') and @data-slick-index='{page_num}']"))
            )
            # Pausa extra para a animação do carrossel terminar antes do próximo print
            time.sleep(1.5) 
            page_num += 1

        except (NoSuchElementException, TimeoutException):
            print(f"  Fim do carrossel (botão next não encontrado ou timeout).")
            break
        except Exception as e:
            print(f"  Erro inesperado ao avançar o carrossel: {e}")
            break

try:
    driver.get(BASE_URL)
    time.sleep(3)

    try:
        clicar_elemento("button.ot-close-icon", timeout=5)
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        nome_loja = re.sub(r'[\\/*?:"<>|\s]', '_', loja)
        
        print(f"\n--- Processando: {estado} - {loja} ---")

        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f"  Região não selecionada: {e}")

        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            if not select_by_visible_text_contains(loja_select, loja):
                raise RuntimeError(f"Loja não encontrada: {loja}")

        time.sleep(0.8)
        clicar_elemento("button.confirmar")
        time.sleep(3)

        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()
        
        download_dir = OUTPUT_DIR / f"encartes_{nome_loja}_{data_nome}"
        download_dir.mkdir(parents=True, exist_ok=True)

        baixar_encartes(1, download_dir)

        for i in range(2, 4):
            try:
                # Verifica se o botão do jornal extra existe antes de tentar clicar
                btn_xpath = f"//button[contains(., 'Jornal de Ofertas {i}')]"
                if driver.find_elements(By.XPATH, btn_xpath):
                    clicar_elemento(btn_xpath, By.XPATH)
                    time.sleep(3)
                    aguardar_elemento("div.ofertas-slider", timeout=30)
                    baixar_encartes(i, download_dir)
            except Exception as e:
                print(f"  Jornal {i} não processado: {e}")

        try:
            clicar_elemento("a.seletor-loja")
            time.sleep(2)
        except:
            pass

    print("\nTodos os encartes foram processados!")

except Exception as e:
    print(f"\nERRO CRÍTICO: {e}")
    try:
        screenshot_path = OUTPUT_DIR / "ERRO_assai_tela_cheia.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"  Screenshot de erro salvo: {screenshot_path}")
    except:
        pass
finally:
    driver.quit()