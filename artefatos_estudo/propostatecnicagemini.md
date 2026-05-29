# 🚀 Proposta Técnica: Calculadora de Custos de Alta Performance

Este documento detalha a estratégia de engenharia para implementar a `CalculadoraCustosB3` no **SpreadHunter** sem degradar a performance do monitoramento em tempo real, evitando gargalos de CPU e latência.

## 1. O Problema: O Custo do Loop O(N²)
Atualmente, as estratégias de BOX e Colar cruzam listas de ativos. Se houver 200 Puts e 200 Calls para um ativo, são 40.000 combinações. Instanciar objetos ou realizar cálculos complexos dentro desse loop em Python puro elevaria o tempo de ciclo drasticamente.

## 2. Estratégia de Performance: Vetorização com NumPy

Para que o cálculo de custos seja "invisível" para o processador, a proposta é utilizar a **Vetorização Esparsa**:

### 2.1. Injeção de Constantes (Fatores Pré-Calculados)
Em vez de calcular taxas complexas para cada perna, a calculadora deve manter um **Fator de Fricção Único** por estratégia, definido na inicialização do sistema:

*   **Fator BOX (4 pernas):** `(0.000250 + 0.000275) * 4 = 0.0021` (Emolumento + Liquidação).
*   **Fator Colar (3 pernas):** `Fator_Opcoes * 2 + Fator_Ativo`.

### 2.2. Otimização do Fluxo de Filtros
A ordem dos fatores altera o produto da performance. O fluxo deve ser:
1.  **Filtro 1:** Liquidez (`qul > 100`).
2.  **Filtro 2:** Distância de Strike (ex: máx 15%).
3.  **Cálculo de Custos:** Apenas sobre o subset que passou nos filtros 1 e 2.

### 2.3. Implementação Matricial
Ao usar NumPy, o custo B3 torna-se uma única operação aritmética de baixo nível:

```python
# Exemplo de lógica vetorizada ultra-rápida
import numpy as np

def verificar_viabilidade_liquida(strikes, lucros_brutos, taxa_cdi_periodo):
    # strikes: array de preços médios das pernas
    # lucros_brutos: array de lucros calculados
    
    # Cálculo em nível de C (milissegundos para milhares de linhas)
    custos_b3 = strikes * 0.0021 
    lucro_liquido = lucros_brutos - custos_b3
    
    viaveis = lucro_liquido > taxa_cdi_periodo
    return viaveis
```

## 3. Minimização de Latência de Memória

*   **Singletons:** A `CalculadoraCustosB3` deve ser instanciada uma única vez e injetada nos monitores.
*   **Lazy Loading:** Os parâmetros de taxas B3 devem ser carregados do banco apenas no *startup*, evitando I/O de disco durante a varredura.

## 4. Conclusão da Proposta

Ao tratar os dados de mercado como **matrizes** e aplicar os custos como um **fator escalar**, o SpreadHunter consegue processar 50.000 opções com precisão financeira real sem adicionar latência perceptível à interface do usuário.

---
*Gerado por Gemini Code Assist — 29/05/2026*