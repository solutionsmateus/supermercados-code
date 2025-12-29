# -*- coding: utf-8 -*-
import os
import re
import time
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


# Novo formato: {UF: [(Cidade, Nome da Loja), ...]}
LOJAS_ESTADOS = {
    "PA": [("Belém", "Belém Portal da Amazônia")],
    "PE": [("Recife", "Recife Avenida Recife")],
    "BA": [
        ("Salvador", "Salvador Garibaldi"),
        ("Vitória Da Conquista", "Vitória da Conquista Brumado")
    ],
    "AL": [("Maceió", "Maceió Praia")],
    "MA": [("São Luís", "São Luís")],
    "CE": [("Fortaleza", "Fortaleza Fátima")],
    "PI": [("Teresina", "Teresina Primavera")],
    "SE": [("Aracaju", "Aracaju Tancredo Neves")],
    "PB": [("João Pessoa", "João Pessoa Bessa")]
}

BASE_URL = "https://www.atacadao.com.br/institucional/nossas-lojas"

BASE_OUTPUT = Path(os.environ.get("OUTPUT_DIR", str(Path.cwd() / "Encartes"))).resolve()
ENCARTE_DIR = BASE_OUTPUT / "Atacadao"
ENCARTE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[atacadao.py] Pasta de saída: {ENCARTE_DIR}")


options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

def encontrar_data():
    try:
        enc_data = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//p[contains(@class, "text-xs text-neutral-400")]'))
        )
    except:
        return "sem_data"
    
    for div in enc_data:
        texto = div.text.strip()
        if texto:
            nome_pasta = re.sub(r'[\\/*?:"<>|\s]', '_', texto)
            return nome_pasta
    return "sem_data"

def clicar_confirmar():
    try:
        confirmar_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Confirmar']"))
        )
        confirmar_button.click()
    except:
        pass  
    

def selecionar_uf_cidade(uf, cidade):
    # O tempo de espera foi aumentado para garantir que os selects carreguem
    Select(wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'md:w-[96px]')]")))).select_by_value(uf)
    time.sleep(2) # Espera um pouco mais
    Select(wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(@class, 'md:w-[360px]')]")))).select_by_visible_text(cidade)
    time.sleep(2) # Espera um pouco mais

def clicar_loja_por_nome(loja_nome):
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='store-card']")))
    lojas = driver.find_elements(By.CSS_SELECTOR, "[data-testid='store-card']")
    for loja in lojas:
        try:
            titulo = loja.find_element(By.TAG_NAME, "h1").text
            if loja_nome.lower() in titulo.lower():
                botao = loja.find_element(By.TAG_NAME, "a")
                print(f"Acessando loja: {titulo}")
                botao.click()
                return titulo
        except Exception as e:
            # print(f"Erro ao processar card de loja: {e}")
            continue
    print(f" Loja '{loja_nome}' não encontrada.")
    return None

def baixar_encartes(uf, cidade, loja_nome):
    print("Buscando encartes...")

    try:
        time.sleep(2)
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'Flyer/?id=')]")

        if not links:
            print("Nenhum link de encarte encontrado.")
            return

      
        # Garante nome de pasta seguro para o sistema de arquivos
        loja_segura = re.sub(r'[\\/*?:"<>|,\n\r]+', "_", loja_nome).strip().replace(" ", "_")
        pasta_destino = ENCARTE_DIR / uf / cidade / loja_segura
        pasta_destino.mkdir(parents=True, exist_ok=True)

        for i, link in enumerate(links, start=1):
            url = link.get_attribute("href")
            if not url:
                continue
            nome_arquivo = f"encarte_{i}.pdf"
            caminho = pasta_destino / nome_arquivo

            try:
                # O requests.get não está usando o User-Agent definido no YAML. Se precisar disso,
                # você teria que passar o User-Agent do ambiente como um header aqui.
                response = requests.get(url, timeout=15) 
                with open(caminho, "wb") as f:
                    f.write(response.content)
                print(f" Baixado: {nome_arquivo}")
            except Exception as e:
                print(f"Erro ao baixar {url}: {e}")

    except Exception as e:
        print(f"Erro ao buscar encartes: {e}")

try:
    driver.get(BASE_URL)
    clicar_confirmar()

    # Loop para iterar sobre o novo formato
    for uf, lojas in LOJAS_ESTADOS.items():
        for cidade, loja_nome in lojas:
            print(f"\n Estado: {uf} | Cidade: {cidade} | Loja: {loja_nome}")
            # Recarrega a página base para garantir que os selects sejam redefinidos
            driver.get(BASE_URL)
            time.sleep(2)
            clicar_confirmar()

            selecionar_uf_cidade(uf, cidade)
            nome_loja_encontrada = clicar_loja_por_nome(loja_nome)

            if nome_loja_encontrada:
                baixar_encartes(uf, cidade, nome_loja_encontrada)
                time.sleep(2)

except Exception as e:
    print(f" Erro geral: {e}")

finally:
    print(" Execução finalizada")
    driver.quit()