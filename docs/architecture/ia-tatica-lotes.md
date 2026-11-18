# IA tática dos bots — decisões e lotes de comportamento

> Parâmetros da IA `provisorio-0.7` (PROVISÓRIO — pendente de aprovação (PB-03)). Motor com parâmetros provisórios
> (`provisorio-0.5`, não calibrado). Gerado por `scripts/tactics_report.py`.

## Decisões em situações típicas (personalidade equilibrada)

| Situação | Postura escolhida |
|---|---|
| Perdendo por 1 aos 80' | ataque_total |
| Vencendo por 1 aos 80' | retranca |
| Empate aos 70' (Liga) | equilibrada |
| Empate aos 70', precisa vencer (título) | ataque_total |
| Empate aos 70', evitar derrota | retranca |
| Vencendo por 1 com 10 jogadores aos 55' | retranca |
| Empate aos 55' contra 10 jogadores | ataque_total |
| Perdendo por 1 aos 70' com elenco exausto (40%) | ataque_total |
| Copa: perdendo por 1 aos 80' | ataque_total |
| Copa: empate aos 75', equipe muito superior | equilibrada |
| Copa: empate aos 75', equipe muito inferior | retranca |

## Personalidades (Liga): moderação

Em situações claras (perdendo/vencendo) todas concordam; a personalidade desloca a decisão nos empates.

| Estado | aggressive | balanced | opportunist | conservative |
|---|---|---|---|---|
| 0×0 30' | equilibrada | equilibrada | equilibrada | equilibrada |
| 0×0 55' | equilibrada | equilibrada | equilibrada | equilibrada |
| 0×0 70' | ataque_total | equilibrada | equilibrada | equilibrada |
| 0×0 85' | ataque_total | equilibrada | ataque_total | equilibrada |
| 0×1 45' | ataque_total | ataque_total | ataque_total | ataque_total |
| 0×1 80' | ataque_total | ataque_total | ataque_total | ataque_total |
| 1×0 45' | retranca | retranca | retranca | retranca |
| 1×0 80' | retranca | retranca | retranca | retranca |
| 0×0 55' contra 10 | ataque_total | ataque_total | ataque_total | ataque_total |

## Lotes de comportamento (times de mesma força)

| Métrica | IA × IA (300 jogos) | IA × estático (400 jogos) |
|---|---|---|
| Partidas inválidas | 0 | 0 |
| Mudanças de postura por equipe/jogo | 1.05 | 0.98 |
| Máximo de mudanças de uma equipe num jogo | 4 | 5 |
| Mudanças que aumentam o ataque quando perdendo | 100% | 100% |
| Mudanças que protegem quando vencendo | 100% | 100% |
| Tempo ofensivo após 75', perdendo | 83% | 80% |
| Tempo defensivo após 75', vencendo | 99% | 99% |
| Pontos por jogo (lado 0 / lado 1) | 1.39 / 1.29 | IA 1.36 / estático 1.33 |

Posturas adotadas (IA × IA): {'retranca': 349, 'ataque_total': 266, 'equilibrada': 13, 'ofensiva': 1}

## Clubes reais: formação e postura inicial escolhidas

Formações candidatas de TESTE (lista oficial pendente — PM-01). Adversário com histórico público
fictício: forte (marcou 12, sofreu 3 em 5 jogos) ou fraco (marcou 3, sofreu 12).

| Clube | Contra adversário forte | Contra adversário fraco |
|---|---|---|
| Flamengo | 5-3-2, equilibrada | 4-4-2, ataque_total |
| Palmeiras | 5-3-2, equilibrada | 4-4-2, ataque_total |
| Botafogo | 5-3-2, retranca | 4-4-2, ataque_total |
| Goiás | 5-3-2, retranca | 4-4-2, ataque_total |
| Londrina | 5-3-2, retranca | 4-3-3, ataque_total |
| São Bernardo | 5-3-2, retranca | 4-4-2, ataque_total |

## Leitura

- As decisões seguem a situação: perdendo → mais ofensivo; vencendo → protege; 'precisa vencer' ataca
  no empate; 'evitar derrota' protege o empate; time inferior na Copa segura o empate para os pênaltis.
- Como as posturas do motor alteram gols marcados e sofridos em proporções próximas (medido), a IA as usa
  principalmente para gerir risco (variância), não para ganhar força: o desempenho contra um time estático
  de mesma força fica no mesmo patamar (sem vantagem artificial).
- Estabilidade: poucas mudanças por partida; ganho mínimo, histerese e intervalo de 10 min, com exceções
  só após gols, expulsões e perdas de jogador.

_Tempo de geração: 36 s._
