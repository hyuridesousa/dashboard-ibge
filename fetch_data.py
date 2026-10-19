"""
Script ETL: Baixa dados do SIDRA/IBGE e a malha territorial das UFs.
Gera os arquivos locais na pasta data/ para garantir alta disponibilidade.
"""
import json
from pathlib import Path
import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SIDRA_URL = "https://apisidra.ibge.gov.br/values/t/4099/n3/all/v/4099/p/all"
GEO_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intradivision=UF"
GEO_FALLBACK = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

SIGLA_TO_CODE = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16",
    "TO": "17", "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
    "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
    "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50",
    "MT": "51", "GO": "52", "DF": "53"
}

def executar_etl():
    print("Baixando série histórica PNAD Contínua (Tabela 4099/IBGE)...")
    resp_sidra = requests.get(SIDRA_URL, headers=HEADERS, timeout=120)
    resp_sidra.raise_for_status()
    linhas = resp_sidra.json()[1:]
    
    df = pd.DataFrame(
        {
            "uf_code": [x["D1C"] for x in linhas],
            "uf": [x["D1N"] for x in linhas],
            "periodo": [x["D3C"] for x in linhas],
            "taxa": [x["V"] for x in linhas],
        }
    )
    caminho_csv = DATA_DIR / "pnad_4099.csv"
    df.to_csv(caminho_csv, index=False)
    print(f"Sucesso: {len(df)} registros salvos em '{caminho_csv}'.")

    print("\nBaixando malha geográfica das UFs (GeoJSON)...")
    try:
        resp_geo = requests.get(GEO_URL, headers=HEADERS, timeout=120)
        resp_geo.raise_for_status()
        geo = resp_geo.json()
    except Exception as e:
        print(f"Aviso: Não foi possível conectar ao servidor principal do IBGE ({e}).")
        print("Obtendo GeoJSON do repositório de reserva...")
        resp_geo = requests.get(GEO_FALLBACK, headers=HEADERS, timeout=120)
        resp_geo.raise_for_status()
        geo = resp_geo.json()
        
        for feat in geo["features"]:
            props = feat.setdefault("properties", {})
            sigla = props.get("sigla") or props.get("postal")
            if sigla in SIGLA_TO_CODE:
                props["uf_code"] = SIGLA_TO_CODE[sigla]

    # Normalização dos códigos de UF na propriedade do GeoJSON
    for feat in geo.get("features", []):
        props = feat.setdefault("properties", {})
        codigo = props.get("codarea") or props.get("CD_UF") or props.get("id") or props.get("uf_code") or feat.get("id")
        if codigo:
            props["uf_code"] = str(codigo)

    caminho_geo = DATA_DIR / "uf.geojson"
    caminho_geo.write_text(json.dumps(geo), encoding="utf-8")
    print(f"Sucesso: {len(geo['features'])} feições salvas em '{caminho_geo}'.")
    print("\nETL concluído com êxito!")

if __name__ == "__main__":
    executar_etl()