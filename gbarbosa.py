import os
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://blog.gbarbosa.com.br/ofertas/"
BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
DOWNLOAD_BASE = BASE_OUTPUT / "G-Barbosa"
DOWNLOAD_BASE.mkdir(parents=True, exist_ok=True)
print(f"[gbarbosa.py] Pasta base de saída: {DOWNLOAD_BASE}")

os.makedirs(DOWNLOAD_BASE, exist_ok=True)

estados_para_baixar = ["AL", "SE", "BA"]

MAX_PAGES_TO_SCROLL = 15  
SCROLL_PAUSE_TIME = 3    

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")


driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 40) # Tempo de espera


def capturar_encarte(driver: webdriver.Chrome, state_sigla: str, page_number: int):
    FLIPBOOK_CONTENT_XPATH = '//div[contains(@class, "df-page-content") and contains(@class, "df-content-loaded")]'
    
    try:
        page_elements = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, FLIPBOOK_CONTENT_XPATH))
        )
        
        target_index = page_number - 1
        
        if page_number <= len(page_elements):
            page_element = page_elements[target_index]
            
            print(f"   -- Movendo o elemento da página {page_number} para visualização...")
            driver.execute_script("arguments[0].scrollIntoView(true);", page_element)
            time.sleep(10) 
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_name = f"GBarbosa_{state_sigla}_Pag{page_number}_{timestamp}.png"
            output_path = DOWNLOAD_BASE / file_name
            
            page_element.screenshot(str(output_path))
            print(f"Screenshot da página {page_number} do estado {state_sigla} salvo.")
            return True
        else:
             print(f"Aviso: Elemento da página {page_number} não encontrado na lista (apenas {len(page_elements)} detectados).")
             return False

    except Exception as e:
        print(f" Erro ao tirar screenshot da página {page_number} ({state_sigla}): {e}")
        return False


def baixar_estado(sigla_estado):
    print(f"\n--- Iniciando Baixando encartes do estado: {sigla_estado} ---")
    driver.get(BASE_URL)
    time.sleep(10)

    try:
        print(f"1. Clicando no botão do estado: {sigla_estado}")
        botao_estado = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f'//button[text()="{sigla_estado}"]'))
        )
        botao_estado.click()
        time.sleep(10) 

        print("2. Buscando e clicando no botão 'Ver Encarte'...")
        
        ver_encarte_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//button[@class="encarte-button" and text()="Ver Encarte"]')
        ))
        ver_encarte_btn.click()
        time.sleep(10) 

        print(f"3. Iniciando scroll e captura (máx. {MAX_PAGES_TO_SCROLL} páginas)...")
        
        SCROLL_CONTAINER_XPATH = '//body' 

        scroll_container = wait.until(
            EC.presence_of_element_located((By.XPATH, SCROLL_CONTAINER_XPATH))
        )
        
        for page_num in range(1, MAX_PAGES_TO_SCROLL + 1):
            
            captured = capturar_encarte(driver, sigla_estado, page_number=page_num)
            
            if not captured and page_num > 1:
                print("Fim do encarte detectado ou erro de carregamento. Parando a captura.")
                break

            if page_num < MAX_PAGES_TO_SCROLL:
                print(f"   -- Rolando a página para carregar a próxima seção do encarte...")
                
                driver.execute_script("window.scrollBy(0, window.innerHeight);")

                time.sleep(SCROLL_PAUSE_TIME) 

    except Exception as e:
        print(f"Erro fatal durante a extração do estado {sigla_estado}: {e}")
    finally:
        driver.get(BASE_URL)
        time.sleep(10)


if __name__ == "__main__":
    for estado in estados_para_baixar:
        baixar_estado(estado)

    driver.quit()
    print("\nProcesso de captura de encartes do GBarbosa concluído.")