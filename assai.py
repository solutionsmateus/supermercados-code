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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException

# --- Configuração de Saída ---
OUTPUT_DIR = Path(os.environ.get("GITHUB_WORKSPACE", "Encartes_Assai")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
def strip_accents(s: str) -> str:
    """Remove acentos e normaliza o texto para comparação."""
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()

def click_robusto(driver, element) -> bool:
    """Tenta clicar em um elemento de forma robusta, usando JavaScript como fallback."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
        time.sleep(0.3) # Pequena pausa para a rolagem acontecer
        element.click()
        return True
    except StaleElementReferenceException:
        print("[AVISO] StaleElementReferenceException ao clicar. Tentando novamente...")
        time.sleep(1) # Espera e tenta novamente
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
            time.sleep(0.3)
            element.click()
            return True
        except Exception as e:
            print(f"[AVISO] Falha persistente ao clicar no elemento após StaleElement: {e}")
            return False
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            print(f"[AVISO] Falha ao clicar no elemento: {e}")
            return False

def select_contains_noaccent(select_el, target_text: str, wait_time=10) -> bool:
    """Seleciona uma opção em um <select> comparando o texto sem acentos."""
    # Espera até que as opções sejam carregadas no select
    WebDriverWait(select_el.parent, wait_time).until(lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 1)
    alvo_normalizado = strip_accents(target_text)
    for option in select_el.find_elements(By.TAG_NAME, "option"):
        if alvo_normalizado in strip_accents(option.text):
            Select(select_el).select_by_visible_text(option.text)
            return True
    return False

def encontrar_data_validade(driver) -> str:
    """Extrai a data de validade das ofertas para nomear a pasta."""
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

def get_current_slide_image_url(driver, wait) -> str:
    """Tenta obter a URL da imagem do slide ativo com várias tentativas e esperas."""
    for attempt in range(5): # Aumenta as tentativas
        try:
            # Procura pela tag <img> dentro do slide ativo que tenha um src válido
            # Adiciona uma espera para o elemento ser visível e ter um atributo src
            img_element = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//div[contains(@class, 'slick-active')]//img[contains(@src, 'assai.com.br')]")
            ))
            src = img_element.get_attribute("src")
            if src and src.startswith("http"):
                return src
            else:
                print(f"  [DEBUG] Tentativa {attempt+1}: SRC da imagem inválido ou vazio: {src}")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"  [DEBUG] Tentativa {attempt+1}: Erro ao encontrar imagem do slide ({type(e).__name__})... Tentando novamente.")
        except StaleElementReferenceException:
            print(f"  [DEBUG] Tentativa {attempt+1}: StaleElementReferenceException ao obter imagem do slide. Re-tentando.")
        time.sleep(1) # Pequena pausa antes de tentar novamente
    return ""

def baixar_encartes_do_jornal(driver, wait, jornal_num: int, download_dir: Path):
    """Baixa todas as páginas de um jornal de ofertas específico."""
    download_dir.mkdir(parents=True, exist_ok=True)
    urls_ja_baixadas = set()
    MAX_PAGES = 30 # Limite de segurança para evitar loops infinitos

    for page_num in range(1, MAX_PAGES + 1):
        try:
            url = get_current_slide_image_url(driver, wait)
            if not url:
                print(f"  [Jornal {jornal_num}] URL da imagem não encontrada no slide {page_num}. Finalizando.")
                break

            if url in urls_ja_baixadas:
                print(f"  [Jornal {jornal_num}] Página repetida detectada ({url}). Finalizando este jornal.")
                break
            
            print(f"  [Jornal {jornal_num}] Baixando página {page_num}: {url}")
            response = requests.get(url, timeout=30, headers={
                'Referer': BASE_URL,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            if response.status_code == 200:
                nome_base = os.path.basename(url).split("?")[0]
                nome_arquivo = f"jornal_{jornal_num}_pagina_{page_num}_{nome_base}"
                filepath = download_dir / nome_arquivo
                with open(filepath, "wb") as f:
                    f.write(response.content)
                urls_ja_baixadas.add(url)
            else:
                print(f"  [ERRO] Falha no download de {url} (Status: {response.status_code})")

            # Tenta avançar para a próxima imagem
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            if "slick-disabled" in next_button.get_attribute("class"):
                print(f"  [Jornal {jornal_num}] Botão 'próximo' desabilitado. Fim do jornal.")
                break
            
            prev_url = url # Guarda a URL atual para verificar a mudança
            click_robusto(driver, next_button)
            
            # Espera a URL da imagem mudar, garantindo que o carrossel avançou
            try:
                # Aumenta o timeout para a mudança de slide
                WebDriverWait(driver, 15).until(lambda d: get_current_slide_image_url(d, wait) != prev_url)
                time.sleep(0.8) # Pequena pausa adicional para renderização
            except TimeoutException:
                print(f"  [Jornal {jornal_num}] Slide não mudou após clicar em 'próximo' dentro do tempo limite. Fim do jornal.")
                break

        except Exception as e:
            print(f"  [Jornal {jornal_num}] Não foi possível encontrar mais páginas ou ocorreu um erro: {type(e).__name__} - {e}. Finalizando.")
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
    # Adiciona o caminho do chromedriver explicitamente
    # No ambiente do GitHub Actions, o chromedriver é instalado em /usr/bin/chromium-chromedriver
    # ou /usr/lib/chromium-browser/chromedriver
    service = webdriver.ChromeService(executable_path="/usr/bin/chromium-chromedriver")
    return webdriver.Chrome(options=options, service=service)

# --- Execução Principal ---
driver = None
try:
    driver = build_headless_chrome()
    wait = WebDriverWait(driver, 30) # Aumentado o tempo de espera padrão para 30s

    print("[INFO] Acessando a página de ofertas...")
    driver.get(BASE_URL)

    # --- Lidar com o modal de seleção de loja primeiro ---
    try:
        # Espera o modal de seleção de loja aparecer
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-loja")))
        print("[INFO] Modal de seleção de loja aberto.")

        # Clica no seletor de loja para abrir o modal (se ainda não estiver aberto ou para reabrir)
        # wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja"))).click()
        # time.sleep(1.5) # Pequena pausa para o modal abrir completamente e elementos carregarem

    except TimeoutException:
        print("[INFO] Modal de seleção de loja não apareceu automaticamente.")
        # Se o modal não apareceu, tenta clicar no seletor de loja
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja"))).click()
            time.sleep(1.5)
            print("[INFO] Modal de seleção de loja aberto via clique.")
        except Exception as e:
            print(f"[AVISO] Não foi possível abrir o modal de seleção de loja: {e}")

    # --- Processar lojas ---
    for estado, loja_alvo in LOJAS_ESTADOS.items():
        print(f"\n--- Processando Estado: {estado}, Loja: {loja_alvo} ---")
        
        try:
            # Seleciona o Estado
            select_estado_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.estado")))
            if not select_contains_noaccent(select_estado_el, estado, wait_time=15): # Aumenta espera para o select
                print(f"  [ERRO] Estado \'{estado}\' não encontrado. Pulando.")
                # Tenta fechar o modal de seleção de loja antes de continuar para o próximo estado
                try:
                    driver.find_element(By.CSS_SELECTOR, "button[title='Close']").click()
                except NoSuchElementException:
                    pass
                continue
            time.sleep(1.5) # Espera carregar regiões/lojas

            # Seleciona a Região (se aplicável)
            if estado in REGIAO_POR_ESTADO:
                try:
                    select_regiao_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.regiao")))
                    if not select_contains_noaccent(select_regiao_el, REGIAO_POR_ESTADO[estado], wait_time=15):
                        print(f"  [AVISO] Região \'{REGIAO_POR_ESTADO[estado]}\' não encontrada para {estado}.")
                    time.sleep(1.5) # Espera carregar lojas da região
                except TimeoutException:
                    print(f"  [AVISO] Seletor de região não apareceu para {estado} dentro do tempo limite.")
                except Exception:
                    print(f"  [AVISO] Erro ao tentar selecionar região para {estado}.")

            # Seleciona a Loja
            select_loja_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.loja")))
            if not select_contains_noaccent(select_loja_el, loja_alvo, wait_time=15):
                print(f"  [ERRO] Loja \'{loja_alvo}\' não encontrada. Pulando.")
                # Tenta fechar o modal de seleção de loja antes de continuar para o próximo estado
                try:
                    driver.find_element(By.CSS_SELECTOR, "button[title='Close']").click()
                except NoSuchElementException:
                    pass
                continue
            
            # Confirma a seleção
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.confirmar"))).click()
            print(f"  [INFO] Loja \'{loja_alvo}\' selecionada.")

            # --- Lidar com o pop-up de cookies APÓS a seleção da loja ---
            try:
                # Tenta o seletor que funcionou na navegação manual
                botao_aceitar_todos = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Aceitar Todos')]")))
                click_robusto(driver, botao_aceitar_todos)
                print("[INFO] Pop-up de cookies fechado (Aceitar Todos). ")
            except TimeoutException:
                try:
                    # Tenta o ID, caso o texto mude ou seja outro botão
                    botao_fechar_cookies = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
                    click_robusto(driver, botao_fechar_cookies)
                    print("[INFO] Pop-up de cookies fechado (ID). ")
                except Exception:
                    print("[INFO] Pop-up de cookies não encontrado ou não clicável.")

            # Aguarda o carregamento das ofertas e baixa os encartes
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
            data_validade = encontrar_data_validade(driver)
            nome_loja_limpo = re.sub(r'[^a-zA-Z0-9_]+', '', loja_alvo.replace(" ", "_"))
            pasta_final = OUTPUT_DIR / f"Assai_{nome_loja_limpo}_{data_validade}"
            
            print(f"  [INFO] Salvando encartes em: {pasta_final}")

            # Baixa o primeiro jornal de ofertas
            baixar_encartes_do_jornal(driver, wait, 1, pasta_final)

            # Tenta encontrar e baixar outros jornais
            for i in range(2, 4):
                try:
                    # Clica na aba do próximo jornal
                    # Aumenta o timeout para encontrar o botão do jornal
                    botao_jornal = wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[contains(., 'Jornal de Ofertas {i}')]")))
                    click_robusto(driver, botao_jornal)
                    print(f"\n[INFO] Trocando para o Jornal de Ofertas {i}")
                    time.sleep(2.5) # Espera o novo conteúdo carregar, aumentado
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
                    baixar_encartes_do_jornal(driver, wait, i, pasta_final)
                except TimeoutException:
                    print(f"  [INFO] Jornal de Ofertas {i} não encontrado ou não carregou a tempo para esta loja. Pulando para o próximo estado.")
                    break # Se não achou o 2, provavelmente não terá o 3
                except Exception as e:
                    print(f"  [INFO] Erro ao tentar acessar Jornal de Ofertas {i} para esta loja: {type(e).__name__} - {e}. Pulando para o próximo estado.")
                    break

        except Exception as e:
            print(f"  [ERRO GRAVE] Ocorreu um erro inesperado ao processar \'{loja_alvo}\': {type(e).__name__} - {e}")
            screenshot_path = OUTPUT_DIR / f"erro_{estado}_{loja_alvo}.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"  [DEBUG] Screenshot de erro salvo em: {screenshot_path}")
            # Tenta fechar o modal de seleção de loja se ele estiver aberto
            try:
                driver.find_element(By.CSS_SELECTOR, "button[title='Close']").click()
            except NoSuchElementException:
                pass

finally:
    if driver:
        driver.quit()
    print("\n[INFO] Processo finalizado.")

