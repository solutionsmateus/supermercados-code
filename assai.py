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
    "Bahia": "Assaí Vitória da Conquista", # CHANGE
}

# CHANGE: Região preferida por estado (usado quando existe select.regiao)
REGIAO_POR_ESTADO = {
    "Bahia": "Interior", # CHANGE: explicitamos a região para BA
}

BASE_URL = "https://www.assai.com.br/ofertas"
# Certifique-se de que a pasta de destino é resolvida corretamente
desktop_path = Path.home() / "Desktop/Encartes-Concorrentes/Assai"

# === HEADLESS CHROME ===
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    # Headless moderno do Chrome
    options.add_argument("--headless=new")
    # Estabilidade em ambientes CI (GitHub Actions, containers, etc.)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    # Tamanho de viewport consistente (substitui start-maximized no headless)
    options.add_argument("--window-size=1920,1080")
    # User-Agent explícito ajuda alguns sites a não “minimizar” conteúdo
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # Idioma (seletivos de loja/estado às vezes dependem do locale)
    options.add_argument("--lang=pt-BR,pt")
    
    # Inicializa o driver sem especificar o caminho, dependendo do PATH
    # Se o Chrome Driver não estiver no PATH, você precisará especificar o 'service'
    return webdriver.Chrome(options=options)

try:
    driver = build_headless_chrome()
except Exception as e:
    print(f"Erro ao inicializar o driver Chrome. Verifique se o ChromeDriver está instalado e no seu PATH: {e}")
    exit()

wait = WebDriverWait(driver, 30)

def encontrar_data():
    """Tenta encontrar a data de validade do encarte para usar no nome da pasta."""
    try:
        # Espera por todos os elementos que podem conter a validade
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            # Remove caracteres inválidos para nome de pasta e substitui espaços por '_'
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    """Espera a presença de um elemento no DOM."""
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR):
    """Espera o elemento ser clicável, rola para ele e clica."""
    element = wait.until(EC.element_to_be_clickable((by, seletor)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()

def scroll_down_and_up():
    """Rola para baixo e volta para forçar o carregamento lazy-load de elementos."""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.5)

def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()
    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        
        # === ERRO CRÍTICO 1 CORRIGIDO: O seletor estava incompleto/incorreto. ===
        # Procura por todos os elementos <img> dentro dos slides ativos/visíveis do carrossel
        try:
            links_download = wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[contains(@class, 'slick-slide') and contains(@class, 'slick-active')]//img")
                ),
                timeout=10 # Tempo de espera reduzido para tentar detectar o fim mais rápido
            )
        except:
            # Se não encontrar mais imagens após a primeira página, assume que o carrossel terminou.
            if page_num > 1:
                break
            # Caso contrário, tenta novamente no loop (pode ser um erro de carregamento)
            links_download = []

        current_page_urls = []
        for link in links_download:
            # === ERRO CRÍTICO 2 CORRIGIDO: O get_attribute estava incompleto. ===
            # Assume que o elemento é um <img> e o URL está no atributo 'src'.
            url = link.get_attribute("src")
            
            if url and url not in downloaded_urls:
                current_page_urls.append(url)
                downloaded_urls.add(url)

        if not current_page_urls and page_num > 1:
            break

        for idx, url in enumerate(current_page_urls, start=1):
            if not url: continue # Pula se a URL estiver vazia por algum motivo
            
            # Garante que a URL é acessível e baixa
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    # Usa o datetime atual no nome do arquivo para garantir unicidade
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    file_path = download_dir / f"encarte_jornal_{jornal_num}_pagina_{page_num}_{idx}_{timestamp}.jpg"
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    print(f"  Encarte {file_path.name} salvo.")
                else:
                    print(f"Falha no download: {url} (Status: {response.status_code})")
            except requests.exceptions.RequestException as req_e:
                 print(f"Erro de requisição ao baixar {url}: {req_e}")

        try:
            # Tenta clicar no botão 'Próximo'
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'ofertas-slider')]//button[contains(@class, 'slick-next')]"))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(2)
            next_button.click()
            time.sleep(2) # Espera o carrossel avançar e carregar novas imagens
            page_num += 1
        except Exception as e:
            # Se não encontrar o botão 'Próximo' (ou se ele for desabilitado), o carrossel terminou
            print(f"Fim do carrossel alcançado ou erro no botão 'Next': {e}")
            break

# CHANGE: helper para selecionar por "contém texto" (robusto contra variações de acento/espaço)
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

# === MAIN SCRIPT EXECUTION ===
try:
    driver.get(BASE_URL)
    time.sleep(2)

    try:
        # Tenta fechar o modal/popup inicial
        clicar_elemento("button.ot-close-icon", timeout=5) 
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f"--- Processando: {estado} - {loja} ---")

        # 1. Seleciona o Estado
        estado_select = aguardar_elemento("select.estado")
        Select(estado_select).select_by_visible_text(estado)
        time.sleep(1)

        # 2. Seleciona a Região (se aplicável)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select_element = aguardar_elemento("select.regiao", timeout=15)
                Select(regiao_select_element).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.5)
            except Exception as e:
                print(f" Não foi possível selecionar a região para {estado}: {e}")

        # 3. Seleciona a Loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            ok = select_by_visible_text_contains(loja_select, loja)
            if not ok:
                raise RuntimeError(f"Não encontrei a loja '{loja}' no estado {estado}")

        time.sleep(0.8)

        # 4. Confirma a Seleção
        clicar_elemento("button.confirmar")
        time.sleep(3) # Espera um pouco mais para o carregamento pós-confirmação

        # 5. Começa a Raspagem
        aguardar_elemento("div.ofertas-slider", timeout=30)
        data_nome = encontrar_data()

        # Prepara o diretório de download
        nome_loja = re.sub(r'[\\/*?:"<>|\s]', '_', loja) # Sanitiza o nome da loja
        download_dir = desktop_path / f"encartes_{nome_loja}_{data_nome}"
        os.makedirs(download_dir, exist_ok=True)

        # Rola para forçar o lazy-load
        scroll_down_and_up()
        baixar_encartes(1, download_dir) # Baixa o primeiro jornal

        # Tenta baixar os jornais 2 e 3 (se existirem)
        for i in range(2, 4):
            try:
                # Clica no botão do próximo jornal (ex: "Jornal de Ofertas 2")
                clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {i}')]", By.XPATH)
                time.sleep(3)
                aguardar_elemento("div.ofertas-slider", timeout=30)
                scroll_down_and_up()
                baixar_encartes(i, download_dir)
            except Exception as e:
                print(f" Jornal {i} indisponível ou erro para {loja}. Tentando o próximo. Erro: {str(e)}")

        # Volta para o seletor de loja para o próximo loop de estado/loja
        clicar_elemento("a.seletor-loja")
        time.sleep(2)

    print("Todos os encartes foram processados e salvos!")

except Exception as e:
    print(f"Erro crítico no processamento principal: {str(e)}")
    try:
        # Salva screenshot para debug em caso de erro
        os.makedirs(desktop_path, exist_ok=True)
        driver.save_screenshot(str(desktop_path / "erro_encartes.png"))
        print(f"Screenshot salvo em {desktop_path / 'erro_encartes.png'}")
    except Exception as _:
        pass
finally:
    driver.quit()
