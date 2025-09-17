import os
import time
import re
import requests
import unicodedata
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# --- Configuração de Saída ---
OUTPUT_DIR = Path(os.environ.get("GITHUB_WORKSPACE", "Encartes_Assai")).resolve()
print(f"[INFO] Pasta de saída configurada para: {OUTPUT_DIR}")

# --- Mapeamentos ---
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
REGIAO_POR_ESTADO = {"Bahia": "Interior"}
BASE_URL = "https://www.assai.com.br/ofertas"

# --- Funções Auxiliares ---
def strip_accents(s: str ) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()

def click_robusto(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
        time.sleep(0.3)
        element.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            print(f"[AVISO] Falha ao clicar no elemento: {e}")
            return False

def select_contains_noaccent(select_el, target_text: str) -> bool:
    alvo_normalizado = strip_accents(target_text)
    for option in select_el.find_elements(By.TAG_NAME, "option"):
        if alvo_normalizado in strip_accents(option.text):
            Select(select_el).select_by_visible_text(option.text)
            return True
    return False

def encontrar_data_validade(driver) -> str:
    try:
        div_validade = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
        texto = div_validade.text.strip()
        if texto:
            return re.sub(r'[\\/*?:"<>|\s]+', '_', texto)
    except Exception:
        pass
    return "sem_data"

# --- NOVA FUNÇÃO DE DOWNLOAD ---
def baixar_encartes_do_jornal(driver, wait, jornal_num: int, download_dir: Path):
    """Baixa todas as páginas de um jornal de ofertas, extraindo o SRC da imagem."""
    download_dir.mkdir(parents=True, exist_ok=True)
    urls_ja_baixadas = set()
    MAX_PAGES = 30

    for page_num in range(1, MAX_PAGES + 1):
        try:
            # ALTERAÇÃO PRINCIPAL: Buscar a tag <img> dentro do slide ativo
            img_ativa = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//div[contains(@class, 'slick-active')]//img[contains(@src, 'assai.com.br')]")
            ))
            url = img_ativa.get_attribute("src")

            if not url:
                print(f"  [Jornal {jornal_num}] URL da imagem não encontrada no slide {page_num}. Finalizando.")
                break

            if url in urls_ja_baixadas:
                print(f"  [Jornal {jornal_num}] Página repetida detectada ({url}). Finalizando este jornal.")
                break
            
            print(f"  [Jornal {jornal_num}] Baixando página {page_num}: {url}")
            response = requests.get(url, timeout=20, headers={'Referer': BASE_URL})
            if response.status_code == 200:
                # Limpa o nome do arquivo para evitar caracteres inválidos da URL
                nome_base = os.path.basename(url).split('?')[0]
                nome_arquivo = f"jornal_{jornal_num}_pagina_{page_num}_{nome_base}"
                filepath = download_dir / nome_arquivo
                with open(filepath, "wb") as f:
                    f.write(response.content)
                urls_ja_baixadas.add(url)
            else:
                print(f"  [ERRO] Falha no download de {url} (Status: {response.status_code})")

            # Tenta avançar para a próxima imagem
            next_button = driver.find_element(By.CSS_SELECTOR, "button.slick-next")
            if "slick-disabled" in next_button.get_attribute("class"):
                print(f"  [Jornal {jornal_num}] Botão 'próximo' desabilitado. Fim do jornal.")
                break
            
            click_robusto(driver, next_button)
            # Espera explícita para a URL da imagem mudar, garantindo que o carrossel avançou
            wait.until(lambda d: d.find_element(By.XPATH, "//div[contains(@class, 'slick-active')]//img").get_attribute("src") != url)
            time.sleep(0.5)

        except Exception as e:
            print(f"  [Jornal {jornal_num}] Não foi possível encontrar mais páginas ou ocorreu um erro: {type(e).__name__}. Finalizando.")
            break

# --- Configuração do WebDriver ---
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=pt-BR")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

# --- Execução Principal ---
driver = None
try:
    driver = build_headless_chrome()
    wait = WebDriverWait(driver, 20)

    print("[INFO] Acessando a página de ofertas...")
    driver.get(BASE_URL)

    try:
        botao_fechar_cookies = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        click_robusto(driver, botao_fechar_cookies)
        print("[INFO] Pop-up de cookies fechado.")
    except Exception:
        print("[INFO] Pop-up de cookies não encontrado.")

    for estado, loja_alvo in LOJAS_ESTADOS.items():
        print(f"\n--- Processando Estado: {estado}, Loja: {loja_alvo} ---")
        
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja"))).click()

            select_estado_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.estado")))
            if not select_contains_noaccent(select_estado_el, estado):
                print(f"  [ERRO] Estado '{estado}' não encontrado. Pulando.")
                continue
            time.sleep(1)

            if estado in REGIAO_POR_ESTADO:
                try:
                    select_regiao_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.regiao")))
                    select_contains_noaccent(select_regiao_el, REGIAO_POR_ESTADO[estado])
                    time.sleep(1)
                except Exception:
                    print(f"  [AVISO] Seletor de região não apareceu para {estado}.")

            select_loja_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.loja")))
            if not select_contains_noaccent(select_loja_el, loja_alvo):
                print(f"  [ERRO] Loja '{loja_alvo}' não encontrada. Pulando.")
                continue
            
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.confirmar"))).click()
            print(f"  [INFO] Loja '{loja_alvo}' selecionada.")

            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
            data_validade = encontrar_data_validade(driver)
            nome_loja_limpo = re.sub(r'[^a-zA-Z0-9_]+', '', loja_alvo.replace(" ", "_"))
            pasta_final = OUTPUT_DIR / f"Assai_{nome_loja_limpo}_{data_validade}"
            
            print(f"  [INFO] Salvando encartes em: {pasta_final}")

            baixar_encartes_do_jornal(driver, wait, 1, pasta_final)

            for i in range(2, 4):
                try:
                    # Usamos um seletor mais genérico para o botão do jornal
                    botao_jornal = driver.find_element(By.XPATH, f"//button[contains(., 'Jornal') and contains(., '{i}')]")
                    click_robusto(driver, botao_jornal)
                    print(f"\n[INFO] Trocando para o Jornal de Ofertas {i}")
                    time.sleep(2)
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
                    baixar_encartes_do_jornal(driver, wait, i, pasta_final)
                except Exception:
                    print(f"  [INFO] Jornal de Ofertas {i} não encontrado para esta loja.")
                    break

        except Exception as e:
            print(f"  [ERRO GRAVE] Ocorreu um erro ao processar '{loja_alvo}': {e}")
            screenshot_path = OUTPUT_DIR / f"erro_{estado}.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"  [DEBUG] Screenshot de erro salvo em: {screenshot_path}")

finally:
    if driver:
        driver.quit()
    print("\n[INFO] Processo finalizado.")
