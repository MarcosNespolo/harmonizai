import os
import glob
import json
import logging
from pathlib import Path

# Configuração de caminhos
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / 'data' / 'raw'
INTERIM_DIR = BASE_DIR / 'data' / 'interim'
LOGS_DIR = BASE_DIR / 'logs'

# Garantir que os diretórios existam
INTERIM_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configuração de log
log_file = LOGS_DIR / 'merge_raw.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("Iniciando o merge bruto dos arquivos JSON...")
    
    # 1. Iterar sobre data/raw/*.json
    json_files = glob.glob(str(RAW_DIR / '*.json'))
    total_files = len(json_files)
    logging.info(f"Encontrados {total_files} arquivos JSON na pasta raw.")
    
    total_wines_before = 0
    unique_wines = {}
    invalid_files = 0
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 2. Para cada arquivo, ler wines[]
                if isinstance(data, dict) and 'wines' in data:
                    wines_list = data['wines']
                elif isinstance(data, list):
                    wines_list = data
                else:
                    logging.warning(f"Estrutura inesperada no arquivo (pulando): {file_path}")
                    invalid_files += 1
                    continue
                
                # 3 e 4. Concatenar e Deduplicar por wine.id (mantendo o mais recente/primeiro lido)
                for wine in wines_list:
                    if not isinstance(wine, dict):
                        continue
                        
                    total_wines_before += 1
                    
                    # Garantir que o objeto ou a chave contenha o ID (Vivino response tipicamente tem id direto ou dentro de wine)
                    # Dependendo da estrutura exata (se é 'id' no top level do item da lista ou 'wine': {'id': ...})
                    # O json inspecionado mostrou: "wines": [{"id": ..., "name": ...}] (pelo inspecionar anterior)
                    wine_id = wine.get('id')
                    
                    if wine_id is None and 'wine' in wine and isinstance(wine['wine'], dict):
                        wine_id = wine['wine'].get('id')

                    if wine_id is not None:
                        # Mantendo o primeiro encontrado
                        if wine_id not in unique_wines:
                            unique_wines[wine_id] = wine
                    else:
                        logging.warning(f"Vinho sem ID encontrado no arquivo {file_path}. Ignorando.")
                        
        except json.JSONDecodeError as e:
            logging.error(f"Arquivo JSON inválido ou truncado: {file_path} - Erro: {e}")
            invalid_files += 1
        except Exception as e:
            logging.error(f"Erro ao processar o arquivo {file_path}: {e}")
            invalid_files += 1

    total_wines_after = len(unique_wines)
    
    # 5. Salvar como JSONL em data/interim/wines_all.jsonl
    output_file = INTERIM_DIR / 'wines_all.jsonl'
    logging.info(f"Salvando {total_wines_after} vinhos únicos em {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for wine_id, wine in unique_wines.items():
                f_out.write(json.dumps(wine, ensure_ascii=False) + '\n')
    except Exception as e:
        logging.error(f"Erro ao salvar o arquivo JSONL: {e}")
        return

    # Checks ao final
    logging.info("Merge finalizado com sucesso!")
    logging.info(f"Total de arquivos lidos: {total_files - invalid_files} de {total_files}")
    logging.info(f"Total de arquivos inválidos/pulados: {invalid_files}")
    logging.info(f"Total de vinhos antes da deduplicação: {total_wines_before}")
    logging.info(f"Total de vinhos após deduplicação: {total_wines_after}")

if __name__ == "__main__":
    main()
