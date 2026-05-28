# Ideas to Future — Spreadhunter

## Filtro Gaussiano / Z-score no Scanner
- Calcular Z-score de cada strike candidato dentro do scanner (não só no plot)
- Usar `OpcoesNetClient.get_variacao()` para obter média e desvio do ativo (~20 pregões)
- Cache da variação por ativo no SQLite (tabela `variacao_ativo`, TTL 1 dia útil)
- 1 request por ativo por dia, evita gargalo HTTP
- Usar Z-score como filtro (ex: excluir strikes com |z| > 2.5) ou ordenar por percentil

## ML / Análise Preditiva
- Tabela `eventos_mercado`: ativo, data, DTE, strikes, prêmios, pct_CDI, Z-scores, etc
- Cada varredura insere uma linha — anos de histórico em megas
- Feature engineering já pronto: Z-score, percentil gaussiano, DTE relativo, spread de strikes
- Modelos possíveis: classificação (vai virar operação?), regressão (retorno esperado), anomalia (prêmio fora da curva), cluster (agrupar setups)
- Scikit-learn resolve 95% dos casos

## Execução Automática (de reativo para proativo)
- Scanner alimenta modelo → probabilidade preditiva
- Se passar do threshold, envia ordem automaticamente pro Profit
- Ordem pendurada "pescando" a operação ótima
- Precisa de integração com a API de ordens do Profit

## Dependências futuras (para considerar)
- pandas — loops → vetorizado (scanners ficam mais limpos)
- scikit-learn — ML
- loguru — logging cleaner
- keyring — credenciais no cofre do SO

## Aceleração Onda 2 — Cache de Liquidez
- Persistir flag `teve_liquidez` no banco por instrumento (cod_put)
- Na inicialização, Onda 2 prioriza instrumentos com `teve_liquidez=True`
- Evita reaprender liquidez a cada execução
- Se não teve liquidez no dia, perde a flag até reprovar

## Aceleração Onda 1
- (pendente de definição)

## Ordenação ATM-first no Calendar Scanner
- No emparelhamento, ordenar calls e puts por proximidade do spot (ATM)
- `peso = 1 - abs(strike - spot) / (spot * 0.05)`
- Processar ATM primeiro, expandindo para OTM/ITM gradualmente
- Evita perder ciclos com séries muito distantes que nunca formam par viável

## Próximos passos (curto prazo)
1. Subir cálculo de Z-score para `CalculadoraColarCalendario` / `ResultadoColar`
2. Criar cache SQLite da variação dos ativos
3. Usar Z-score como filtro no scanner
4. Tabela `eventos_mercado` com histórico das varreduras
5. Cache de liquidez entre execuções (flag `teve_liquidez`)
6. Priorizar Onda 2 por histórico de liquidez
