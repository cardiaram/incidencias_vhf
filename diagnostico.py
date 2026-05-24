# diagnostico.py
import json

try:
    with open('data/incidencias.json', 'r', encoding='utf-8') as f:
        incidencias = json.load(f)
    
    print(f"Total de incidencias: {len(incidencias)}")
    print("\n=== ÚLTIMAS 3 INCIDENCIAS ===\n")
    
    for inc in incidencias[-3:]:
        print(f"ID: {inc.get('id')}")
        print(f"  remoto: {inc.get('remoto')}")
        print(f"  presencial: {inc.get('presencial')}")
        print(f"  acessos: {inc.get('acessos')}")
        print(f"  viagens: {inc.get('viagens')}")
        print("---")
    
    # Ver la última incidencia en detalle
    if incidencias:
        ultima = incidencias[-1]
        print(f"\n=== DETALHE DA ÚLTIMA INCIDÊNCIA (ID: {ultima.get('id')}) ===")
        print(f"Chaves principais: {list(ultima.keys())}")
        
        if 'remoto' in ultima:
            print(f"remoto: {ultima['remoto']}")
        else:
            print("remoto: NÃO EXISTE")
            
        if 'presencial' in ultima:
            print(f"presencial: {ultima['presencial']}")
        else:
            print("presencial: NÃO EXISTE")
            
except FileNotFoundError:
    print("Arquivo data/incidencias.json não encontrado")
except Exception as e:
    print(f"Erro: {e}")