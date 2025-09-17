import os
import time
import unicodedata
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import re

# === SAÍDA PADRONIZADA (ARTIFACT) ============================================
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"[assai.py] Pasta de saída: {OUTPUT_DIR}")
# ============================================================================

# Mapeamento Estado -> Nome da Loja
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

# Região preferida por estado (quando o site exibe select.regiao)
REGIAO_POR_ESTADO = {"Bahia": "Interior"}

BASE_URL = "https://www.assai.com.br/ofertas"

# === Helpers de normalização/clique ==========================================
def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()

def click_robusto(driver, el) -> bool:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)
        el.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

# === HEADLESS CHROME =========================================================
def build_headless_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR,pt")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)

driver = build_headless_chrome()
wait = WebDriverWait(driver, 30)

# === HELPERS =================================================================
def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class,"ofertas-tab-validade")]'))
        )
    except:
        return "sem_data"
    for div in enc_data:
        texto = (div.text or "").strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]+', '_', texto)
            return nome_pasta[:80]
    return "sem_data"

def aguardar_elemento(seletor, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, seletor)))

def clicar_elemento(seletor, by=By.CSS_SELECTOR):
    element = wait.until(EC.element_to_be_clickable((by, seletor)))
    if not click_robusto(driver, element):
        raise RuntimeError(f"Não consegui clicar em: {seletor}")

def scroll_down_and_up():
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
    time.sleep(0.4)
    driver.execute_script("window.scrollTo(0, 1);")
    time.sleep(0.4)

def select_contains_noaccent(select_el, target_text, timeout=10) -> bool:
    WebDriverWait(driver, timeout).until(lambda d: len(select_el.find_elements(By.TAG_NAME, "option")) > 0)
    alvo = strip_accents(target_text)
    opts = select_el.find_elements(By.TAG_NAME, "option")
    for o in opts:
        if alvo in strip_accents(o.text):
            Select(select_el).select_by_visible_text(o.text)
            return True
    return False

def get_slide_img():
    """Retorna o elemento <img> do slide atual e o src (ou (None, None) se não achar)."""
    try:
        img = wait.until(EC.visibility_of_element_located((
            By.XPATH,
            "//div[contains(@class,'ofertas-slider')]//img[contains(@src,'.jp') or contains(@src,'.png')]"
        )))
        src = img.get_attribute("src") or ""
        return img, src
    except Exception:
        return None, None

def screenshot_slide(download_dir: Path, jornal_num: int, page_num: int) -> tuple[bool, str]:
    """
    Faz screenshot do <img> visível e retorna (ok, src_atual).
    """
    img, src = get_slide_img()
    if not img:
        print(f"  Nenhuma imagem visível no slider (j{jornal_num} p{page_num}).")
        return False, ""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img)
        time.sleep(0.2)
        filepath = download_dir / f"encarte_j{jornal_num}_p{page_num}.png"
        img.screenshot(str(filepath))
        print(f"  Screenshot salvo: {filepath}")
        return True, src
    except Exception as e:
        print(f"  Falha ao capturar screenshot (j{jornal_num} p{page_num}): {e}")
        return False, src

def wait_slide_change(prev_src: str, timeout: float = 6.0) -> bool:
    """
    Aguarda o src do slide mudar (até timeout). Retorna True se mudou.
    """
    end = time.time() + timeout
    while time.time() < end:
        _, curr = get_slide_img()
        if curr and curr != prev_src:
            return True
        time.sleep(0.2)
    return False

def clicar_jornal(i: int) -> bool:
    """Tenta clicar no botão da aba do Jornal i usando seletores alternativos."""
    candidatos = [
        f"//button[contains(., 'Jornal de Ofertas {i}')]",
        f"//button[contains(., 'Jornal {i}')]",
        f"//button[contains(., '{i}') and contains(., 'Jornal')]",
        f"(//button[contains(., 'Jornal')])[{i}]"
    ]
    for xp in candidatos:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            if click_robusto(driver, btn):
                return True
        except Exception:
            continue
    return False

def baixar_encartes(jornal_num: int, download_dir: Path):
    MAX_PAGES = 20  # hard cap para evitar loop infinito
    page_num = 1
    seen_srcs = set()
    download_dir.mkdir(parents=True, exist_ok=True)

    while page_num <= MAX_PAGES:
        print(f"  Baixando página {page_num} do jornal {jornal_num}...")
        ok, src = screenshot_slide(download_dir, jornal_num, page_num)
        if not ok and page_num == 1:
            # Não há imagem/slider ativo — nada para baixar neste jornal
            break

        if src:
            if src in seen_srcs:
                print("  Slide repetido detectado — encerrando este jornal.")
                break
            seen_srcs.add(src)

        # Tentar ir para a próxima página
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.slick-next")))
            # Alguns carrosseis não desabilitam o botão; checamos mudança de slide
            prev_src = src
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
            time.sleep(0.2)
            if not click_robusto(driver, next_button):
                print("  Botão 'próximo' não clicável — encerrando jornal.")
                break

            # Espera slide mudar; se não mudar, encerra
            if not wait_slide_change(prev_src, timeout=6.0):
                print("  Slide não mudou após 'próximo' — encerrando jornal.")
                break

            time.sleep(0.6)
            page_num += 1
        except Exception:
            print("  Não foi possível avançar o slider — encerrando jornal.")
            break

# === MAIN ====================================================================
try:
    driver.get(BASE_URL)
    time.sleep(2)

    # Fecha eventual popup de cookies
    try:
        clicar_elemento("button.ot-close-icon")
    except:
        pass

    clicar_elemento("a.seletor-loja")
    time.sleep(1)

    for estado, loja in LOJAS_ESTADOS.items():
        print(f" Processando: {estado} - {loja}")

        # Estado
        estado_select = aguardar_elemento("select.estado")
        try:
            Select(estado_select).select_by_visible_text(estado)
        except:
            ok = select_contains_noaccent(estado_select, estado)
            if not ok:
                print(f"  Estado '{estado}' não encontrado — pulando.")
                continue
        time.sleep(0.6)

        # Região (quando existir)
        if estado in REGIAO_POR_ESTADO:
            try:
                regiao_select = aguardar_elemento("select.regiao", timeout=15)
                ok = select_contains_noaccent(regiao_select, REGIAO_POR_ESTADO[estado])
                if not ok:
                    print(f"  Aviso: região '{REGIAO_POR_ESTADO[estado]}' não encontrada para {estado}")
                aguardar_elemento("select.loja option[value]", timeout=20)
                time.sleep(0.3)
            except Exception as e:
                print(f"  Não foi possível selecionar a região para {estado}: {e}")

        # Loja
        loja_select = aguardar_elemento("select.loja", timeout=20)
        try:
            Select(loja_select).select_by_visible_text(loja)
        except:
            ok = select_contains_noaccent(loja_select, loja)
            if not ok:
                print(f"  Loja '{loja}' não encontrada em {estado} — pulando.")
                continue

        time.sleep(0.5)

        # Confirmar
        try:
            clicar_elemento("button.confirmar")
        except Exception as e:
            print(f"  Não consegui confirmar a loja ({loja}) — pulando estado. Erro: {e}")
            continue

        # Aguarda slider; se não vier, pula
        try:
            aguardar_elemento("div.ofertas-slider", timeout=30)
        except Exception:
            print("  Slider de ofertas não apareceu — pulando estado.")
            # Volta para selecionar outra loja/estado
            try:
                clicar_elemento("a.seletor-loja")
            except:
                pass
            continue

        data_nome = encontrar_data()
        nome_loja = re.sub(r'[\\/*?:"<>|\s]+', '_', loja)
        pasta_loja_data = OUTPUT_DIR / f"assai_{nome_loja}_{data_nome}"
        pasta_loja_data.mkdir(parents=True, exist_ok=True)
        print(f"  Salvando em: {pasta_loja_data}")

        scroll_down_and_up()
        baixar_encartes(1, pasta_loja_data)

        # Demais jornais (2 e 3)
        for i in range(2, 4):
            try:
                if clicar_jornal(i):
                    time.sleep(1.2)
                    try:
                        aguardar_elemento("div.ofertas-slider", timeout=20)
                        scroll_down_and_up()
                        baixar_encartes(i, pasta_loja_data)
                    except Exception:
                        print(f"  Slider não carregou no Jornal {i}.")
                else:
                    print(f"  Jornal {i} não encontrado para {loja}.")
            except Exception as e:
                print(f"  Jornal {i} indisponível para {loja}: {e}")

        # Volta ao seletor para próximo estado
        try:
            clicar_elemento("a.seletor-loja")
        except:
            pass
        time.sleep(0.8)

    print("Todos os encartes foram processados!")

except Exception as e:
    print(f"Erro crítico: {e}")
    try:
        (OUTPUT_DIR / "debug").mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str((OUTPUT_DIR / "debug" / "erro_encartes.png").resolve()))
        print(f"Screenshot de erro salvo em: {(OUTPUT_DIR / 'debug' / 'erro_encartes.png').resolve()}")
    except Exception:
        pass
finally:
    driver.quit()
