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

# === CONFIGURAÇÕES ===
LOJAS_ESTADOS = {
    "Bahia": "Assaí Atacadista - Vitória da Conquista",
    "Maranhão": "Assaí Atacadista - São Luís Angelim",
    "Ceará": "Assaí Atacadista - Fortaleza Bezerra de Menezes",
    "Pará": "Assaí Atacadista - Belém",
    "Paraíba": "Assaí Atacadista - João Pessoa Geisel",
    "Pernambuco": "Assaí Atacadista - Recife",
    "Piauí": "Assaí Atacadista - Teresina",
    "Sergipe": "Assaí Atacadista - Aracaju",
    "Alagoas": "Assaí Atacadista - Maceió Farol",
}

REGIAO_POR_ESTADO = {
    "Bahia": "Interior",
    # Adicione outras regiões se necessário
}

BASE_URL = "https://www.assai.com.br/ofertas"
desktop_path = Path.home() / "Desktop" / "Encartes-Concorrentes" / "Assai"
os.makedirs(desktop_path, exist_ok=True)


# === FUNÇÕES AUXILIARES ===
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, seletor))
    )


def clicar_elemento(seletor, by=By.CSS_SELECTOR, timeout=20):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, seletor))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()


def fechar_alerta_se_existir():
    try:
        alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
        texto = alert.text
        print(f"Alerta detectado: {texto}")
        alert.accept()
        time.sleep(1)
        return True
    except:
        return False


def select_by_visible_text_contains(select_el, target_text, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 1
        )
        sel = Select(select_el)
        opts = select_el.find_elements(By.TAG_NAME, "option")
        alvo_norm = target_text.strip().lower()
        for o in opts:
            if o.get_attribute("value") and alvo_norm in o.text.strip().lower():
                sel.select_by_visible_text(o.text)
                return True
        return False
    except:
        return False


def encontrar_data():
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


def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.8)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.8)


def baixar_encartes(jornal_num, download_dir):
    page_num = 1
    downloaded_urls = set()

    while True:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        try:
            imgs = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[contains(@class, 'slick-slide') and contains(@class, 'slick-active')]//img")
                )
            )
        except:
            if page_num > 1:
                break
            imgs = []

        current_urls = []
        for img in imgs:
            url = img.get_attribute("src") or img.get_attribute("data-lazy")
            if url and "http" in url and url not in downloaded_urls:
                current_urls.append(url)
                downloaded_urls.add(url)

        if not current_urls and page_num > 1:
            break

        for idx, url in enumerate(current_urls, 1):
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    ext = url.split(".")[-1].split("?")[0]
                    file_path = download_dir / f"jornal_{jornal_num}_pag_{page_num}_{idx}_{timestamp}.{ext}"
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    print(f"  Salvo: {file_path.name}")
                else:
                    print(f"  Falha {response.status_code}: {url}")
            except Exception as e:
                print(f"  Erro ao baixar {url}: {e}")

        try:
            next_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next"))
            )
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(2.5)
            page_num += 1
        except:
            print(f"  Fim do carrossel (jornal {jornal_num})")
            break


# === INÍCIO DO DRIVER ===
try:
    driver = build_headless_chrome()
    wait = WebDriverWait(driver, 30)
    driver.get(BASE_URL)
    time.sleep(3)

    # Fechar popup de cookies se existir
    try:
        clicar_elemento("button.ot-close-icon", timeout=5)
    except:
        pass

    # Abrir seletor de loja
    clicar_elemento("a.seletor-loja")
    time.sleep(2)

    # === LOOP POR ESTADO/LOJA ===
    for estado, loja_desejada in LOJAS_ESTADOS.items():
        print(f"\nProcessando: {estado} → {loja_desejada}")

        try:
            # 1. Selecionar Estado
            estado_select = aguardar_elemento("select.estado")
            Select(estado_select).select_by_visible_text(estado)
            time.sleep(1.5)

            # 2. Selecionar Região (se aplicável)
            if estado in REGIAO_POR_ESTADO:
                try:
                    regiao_select = aguardar_elemento("select.regiao", timeout=15)
                    Select(regiao_select).select_by_visible_text(REGIAO_POR_ESTADO[estado])
                    aguardar_elemento("select.loja option[value!='']", timeout=20)
                    time.sleep(2)
                except Exception as e:
                    print(f"  Região não disponível: {e}")

            # 3. Selecionar Loja
            loja_select = aguardar_elemento("select.loja", timeout=20)
            options = loja_select.find_elements(By.TAG_NAME, "option")
            if len(options) <= 1:
                print(f"  Nenhuma loja disponível em {estado}")
                clicar_elemento("a.seletor-loja")
                time.sleep(1)
                continue

            # Tentar seleção exata
            try:
                Select(loja_select).select_by_visible_text(loja_desejada)
                print(f"  Loja selecionada: {loja_desejada}")
            except:
                if not select_by_visible_text_contains(loja_select, loja_desejada):
                    print(f"  Loja não encontrada: {loja_desejada}")
                    print("  Opções disponíveis:")
                    for opt in options[1:5]:
                        print(f"    - {opt.text}")
                    clicar_elemento("a.seletor-loja")
                    time.sleep(1)
                    continue
                else:
                    print(f"  Loja selecionada (parcial): {loja_desejada}")

            # 4. Confirmar com tratamento de alerta
            try:
                btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.confirmar"))
                )
                driver.execute_script("arguments[0].click();", btn)

                if fechar_alerta_se_existir():
                    print("  Alerta 'Selecione uma loja' → pulando")
                    clicar_elemento("a.seletor-loja")
                    time.sleep(1)
                    continue

                time.sleep(4)

            except Exception as e:
                print(f"  Erro ao confirmar: {e}")
                fechar_alerta_se_existir()
                clicar_elemento("a.seletor-loja")
                time.sleep(1)
                continue

            # 5. Baixar encartes
            try:
                aguardar_elemento("div.ofertas-slider", timeout=30)
                data_nome = encontrar_data()
                nome_loja = re.sub(r'[\\/*?:"<>|]', '_', loja_desejada)
                download_dir = desktop_path / f"{nome_loja}_{data_nome}"
                os.makedirs(download_dir, exist_ok=True)

                scroll_down_and_up()
                baixar_encartes(1, download_dir)

                # Tentar jornais 2 e 3
                for j in range(2, 4):
                    try:
                        clicar_elemento(f"//button[contains(., 'Jornal de Ofertas {j}')]", By.XPATH, timeout=8)
                        time.sleep(3)
                        aguardar_elemento("div.ofertas-slider", timeout=20)
                        scroll_down_and_up()
                        baixar_encartes(j, download_dir)
                    except:
                        break  # Sem mais jornais

                print(f"  Concluído: {estado} - {loja_desejada}")

            except Exception as e:
                print(f"  Erro ao processar encarte: {e}")

            # Voltar ao seletor
            try:
                clicar_elemento("a.seletor-loja")
                time.sleep(2)
            except:
                driver.get(BASE_URL)
                time.sleep(3)
                clicar_elemento("a.seletor-loja")
                time.sleep(2)

        except Exception as e:
            print(f"  Erro grave em {estado}: {e}")
            fechar_alerta_se_existir()

    print("\nTodos os encartes foram processados!")

except Exception as e:
    print(f"\nErro crítico: {e}")
    try:
        screenshot_path = desktop_path / "ERRO_FATAL.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"Screenshot salvo: {screenshot_path}")
    except:
        pass
finally:
    try:
        driver.quit()
    except:
        pass
