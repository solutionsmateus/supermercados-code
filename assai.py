# -*- coding: utf-8 -*-
# assai.py — Headless + OUTPUT_DIR + URLs relativas normalizadas (todas as lojas)
# Autor: você + ajustes ChatGPT
# Uso: python assai.py

import os
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

# ==========================================
# Configuração de saída (compatível com Actions)
# ==========================================
OUTPUT_DIR = Path(
    os.environ.get("OUTPUT_DIR")
    or os.environ.get("GITHUB_WORKSPACE")
    or "Encartes_Assai"
).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[INFO] Pasta de saída configurada para: {OUTPUT_DIR}")

# Usado como referer padrão; a base exata de cada loja virá de driver.current_url
REFERER_BASE = "https://www.assai.com.br/ofertas"

# ==========================================
# Mapeamentos
# ==========================================
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

# ==========================================
# Utilidades
# ==========================================
def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower().strip()

def click_robusto(driver, element) -> bool:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element
        )
        time.sleep(0.25)
        element.click()
        return True
    except StaleElementReferenceException:
        time.sleep(0.6)
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element
            )
            time.sleep(0.25)
            element.click()
            return True
        except Exception as e:
            print(f"[AVISO] Falha ao clicar (stale persistente): {e}")
            return False
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            print(f"[AVISO] Falha ao clicar com JS: {e}")
            return False

def wait_options_loaded(driver, select_el, min_count=1, timeout=15):
    WebDriverWait(driver, timeout).until(
        lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) >= min_count
    )

def select_contains_noaccent(driver, select_el, target_text: str, wait_time=15) -> bool:
    wait_options_loaded(driver, select_el, min_count=1, timeout=wait_time)
    alvo_norm = strip_accents(target_text)
    for opt in select_el.find_elements(By.TAG_NAME, "option"):
        if alvo_norm in strip_accents(opt.text):
            Select(select_el).select_by_visible_text(opt.text)
            return True
    return False

def encontrar_data_validade(driver) -> str:
    try:
        div_validade = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, '//div[contains(@class, "ofertas-tab-validade")]')
            )
        )
        texto = (div_validade.text or "").strip()
        if texto:
            return re.sub(r'[\\/*?:"<>|\s]+', '_', texto)
    except Exception:
        pass
    return "sem_data"

def get_base_context(driver):
    """
    Usa a URL atual da página após confirmar a loja para normalizar caminhos relativos.
    Retorna: (base_page_url, base_origin)
    """
    page_url = driver.current_url.split("#")[0]
    p = urlparse(page_url)
    origin = f"{p.scheme}://{p.netloc}"
    # Em alguns casos, a página pode ser rota sem trailing slash: urljoin lida com isso,
    # mas manteremos a forma simples.
    return page_url, origin

def normalize_url(u: str, base_page_url: str, base_origin: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    # //cdn... -> mantém mesmo esquema da page
    if u.startswith("//"):
        return f"{urlparse(base_page_url).scheme}:{u}"
    # /path -> junta com a origem
    if u.startswith("/"):
        return urljoin(base_origin, u)
    # ./arquivo.jpg ou "arquivo.jpg" -> com base na página atual
    return urljoin(base_page_url if base_page_url.endswith("/") else base_page_url + "/", u)

def get_current_slide_image_url(driver, wait, base_page_url, base_origin) -> str:
    # Pega img do slide atual (slick-current ou slick-active), sem exigir domínio
    for _ in range(5):
        try:
            img = wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//div[contains(@class,'slick-current') or contains(@class,'slick-active')]//img")
                )
            )
            src = (img.get_attribute("src") or "").strip()
            if src:
                return normalize_url(src, base_page_url, base_origin)
        except Exception:
            time.sleep(0.8)
    return ""

def baixar_encartes_do_jornal(driver, wait, jornal_num: int, download_dir: Path, base_page_url: str, base_origin: str):
    """
    Percorre o carrossel do jornal atual e salva as imagens.
    Avança com button.slick-next e para quando a URL repetir ou o botão desabilitar.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    urls_ja_baixadas = set()
    MAX_PAGES = 40  # trava de segurança

    for page_num in range(1, MAX_PAGES + 1):
        try:
            url_img = get_current_slide_image_url(driver, wait, base_page_url, base_origin)
            if not url_img:
                print(f"  [J{jornal_num}] Slide {page_num}: sem URL de imagem. Fim do jornal.")
                break

            if url_img in urls_ja_baixadas:
                print(f"  [J{jornal_num}] Página repetida detectada. Fim do jornal.")
                break

            print(f"  [J{jornal_num}] Baixando página {page_num}: {url_img}")
            try:
                resp = requests.get(
                    url_img, timeout=60,
                    headers={
                        "Referer": base_page_url or REFERER_BASE,
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    },
                )
                if resp.status_code == 200:
                    nome_base = os.path.basename(urlparse(url_img).path)
                    nome_arquivo = f"jornal_{jornal_num}_pagina_{page_num}_{nome_base}"
                    filepath = download_dir / nome_arquivo
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    urls_ja_baixadas.add(url_img)
                else:
                    print(f"  [ERRO] HTTP {resp.status_code} ao baixar {url_img}")
            except Exception as e:
                print(f"  [ERRO] Download falhou ({type(e).__name__}): {e}")

            # Avança no carrossel
            try:
                nxt = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
                if "slick-disabled" in (nxt.get_attribute("class") or ""):
                    print(f"  [J{jornal_num}] Botão 'próximo' desabilitado. Fim.")
                    break

                prev = url_img
                click_robusto(driver, nxt)

                # espera a imagem mudar
                def slidou(_):
                    nxt_url = get_current_slide_image_url(driver, wait, base_page_url, base_origin)
                    return nxt_url and nxt_url != prev

                try:
                    WebDriverWait(driver, 15).until(slidou)
                    time.sleep(0.6)  # pequena pausa extra
                except TimeoutException:
                    print(f"  [J{jornal_num}] Slide não mudou a tempo. Fim.")
                    break
            except TimeoutException:
                print(f"  [J{jornal_num}] Botão 'próximo' não encontrado. Fim.")
                break

        except Exception as e:
            print(f"  [J{jornal_num}] Erro inesperado ({type(e).__name__}): {e}. Fim do jornal.")
            break

# ==========================================
# WebDriver (Headless estável p/ CI)
# ==========================================
def build_headless_chrome():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=pt-BR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Deixe o Selenium Manager resolver o driver (não fixe paths)
    return webdriver.Chrome(options=options)

# ==========================================
# Execução principal
# ==========================================
def main():
    driver = build_headless_chrome()
    wait = WebDriverWait(driver, 30)

    try:
        print("[INFO] Acessando a página de ofertas...")
        driver.get(REFERER_BASE)

        # Abre/garante modal de seleção de loja
        try:
            # às vezes abre sozinho
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-loja")))
            print("[INFO] Modal de seleção de loja detectado.")
        except TimeoutException:
            print("[INFO] Modal não abriu sozinho; tentando abrir pelo seletor.")
            try:
                btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja")))
                click_robusto(driver, btn)
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-loja")))
                print("[INFO] Modal aberto.")
            except Exception as e:
                print(f"[AVISO] Não foi possível abrir o modal de seleção: {e}")

        # Itera estados/lojas
        for estado, loja_alvo in LOJAS_ESTADOS.items():
            print(f"\n--- Processando Estado: {estado} | Loja: {loja_alvo} ---")
            try:
                # Estado
                select_estado = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.estado")))
                if not select_contains_noaccent(driver, select_estado, estado, wait_time=20):
                    print(f"  [ERRO] Estado '{estado}' não encontrado. Pulando.")
                    # Fecha modal, se aberto
                    try:
                        driver.find_element(By.CSS_SELECTOR, "button[title='Close']").click()
                    except NoSuchElementException:
                        pass
                    continue
                time.sleep(1.0)

                # Região (se aplicável)
                if estado in REGIAO_POR_ESTADO:
                    try:
                        select_regiao = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.regiao")))
                        if not select_contains_noaccent(driver, select_regiao, REGIAO_POR_ESTADO[estado], wait_time=20):
                            print(f"  [AVISO] Região '{REGIAO_POR_ESTADO[estado]}' não encontrada para {estado}.")
                        time.sleep(0.8)
                    except TimeoutException:
                        print(f"  [AVISO] Seletor de região não apareceu para {estado}.")

                # Loja
                select_loja = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.loja")))
                if not select_contains_noaccent(driver, select_loja, loja_alvo, wait_time=20):
                    print(f"  [ERRO] Loja '{loja_alvo}' não encontrada. Pulando.")
                    try:
                        driver.find_element(By.CSS_SELECTOR, "button[title='Close']").click()
                    except NoSuchElementException:
                        pass
                    continue

                # Confirmar
                btn_conf = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.confirmar")))
                click_robusto(driver, btn_conf)
                print(f"  [INFO] Loja selecionada.")

                # Cookies (onetrust) — tenta aceitar
                try:
                    try:
                        btn_accept_all = WebDriverWait(driver, 7).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Aceitar Todos')]"))
                        )
                        click_robusto(driver, btn_accept_all)
                        print("  [INFO] Cookies: Aceitar Todos (texto).")
                    except TimeoutException:
                        btn_accept_id = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                        )
                        click_robusto(driver, btn_accept_id)
                        print("  [INFO] Cookies: Aceitar (ID).")
                except Exception:
                    pass

                # Aguarda slider de ofertas
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
                data_validade = encontrar_data_validade(driver)
                nome_loja_limpo = re.sub(r'[^a-zA-Z0-9_]+', '', loja_alvo.replace(" ", "_"))
                pasta_final = OUTPUT_DIR / f"Assai_{nome_loja_limpo}_{data_validade}"
                print(f"  [INFO] Salvando em: {pasta_final}")

                # Base para normalizar URLs relativas desta loja
                base_page_url, base_origin = get_base_context(driver)

                # Jornal 1
                baixar_encartes_do_jornal(driver, wait, 1, pasta_final, base_page_url, base_origin)

                # Jornal 2 e 3 (se existirem)
                for i in range(2, 4):
                    try:
                        botao_jornal = WebDriverWait(driver, 6).until(
                            EC.element_to_be_clickable((By.XPATH, f"//button[contains(., 'Jornal de Ofertas {i}')]"))
                        )
                        click_robusto(driver, botao_jornal)
                        print(f"  [INFO] Trocando para Jornal de Ofertas {i}")
                        time.sleep(2.0)
                        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ofertas-slider")))
                        # Atualiza base (por segurança, caso a rota mude ao trocar o jornal)
                        base_page_url, base_origin = get_base_context(driver)
                        baixar_encartes_do_jornal(driver, wait, i, pasta_final, base_page_url, base_origin)
                    except TimeoutException:
                        print(f"  [INFO] Jornal {i} não disponível para esta loja.")
                        break
                    except Exception as e:
                        print(f"  [INFO] Erro ao acessar Jornal {i}: {type(e).__name__}: {e}")
                        break

                # Volta a abrir o seletor para próxima loja
                try:
                    btn_sel = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja"))
                    )
                    click_robusto(driver, btn_sel)
                    WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-loja"))
                    )
                except Exception:
                    print("  [AVISO] Não foi possível reabrir o seletor de loja; tentando seguir assim mesmo.")

            except Exception as e:
                print(f"  [ERRO] Falha ao processar '{estado} - {loja_alvo}': {type(e).__name__}: {e}")
                # Salva debug
                try:
                    shot = OUTPUT_DIR / f"erro_{estado}_{nome_loja_limpo}.png"
                    driver.save_screenshot(str(shot))
                    (OUTPUT_DIR / f"erro_{estado}_{nome_loja_limpo}.html").write_text(
                        driver.page_source, encoding="utf-8"
                    )
                    print(f"  [DEBUG] Screenshot/HTML salvos em {shot.parent}")
                except Exception:
                    pass
                # tenta reabrir modal para seguir para próxima
                try:
                    btn_sel = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.seletor-loja"))
                    )
                    click_robusto(driver, btn_sel)
                    WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-loja"))
                    )
                except Exception:
                    pass

        print("\n[INFO] Todos os encartes foram processados.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        print("[INFO] Processo finalizado.")
        

if __name__ == "__main__":
    main()
