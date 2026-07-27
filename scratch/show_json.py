import json, sys

data = json.load(sys.stdin)
print(f"Total de parametros: {len(data['parametros'])}\n")

for p in data['parametros']:
    chave = p['chave']
    valor = p['valor']
    estr = p['estrategia']
    desc = p.get('descricao', '')
    print(f"{chave:45s} = {valor:10s}  [{estr:20s}]  {desc}")
