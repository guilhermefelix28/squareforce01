# Calibração estatística — homologação (Entrega 9)

Gerado por `scripts/homologation_calibration.py` (20250 partidas simuladas em 343 s, 10 processos; motor `calibrado-0.7`). Faixas de `criterios.md` (commit `d2cda8e`, anterior a este lote).

Lotes: amplo 10000 (40 clubes REAIS da base, escalação/formação/posturas pela IA, personalidades e situações variadas, 20% eliminatórias) · posturas 5000 · qualidade 3000 · formações 2250.

## Veredito por critério

| Critério | Observado | Resultado |
|---|---|---|
| goals | 2.368 ∈ [2.2, 3.56] | ✅ dentro |
| draw_pct | 25.400 ∈ [22.5, 33.0] | ✅ dentro |
| shots | 24.469 ∈ [22.1, 30.1] | ✅ dentro |
| xg | 2.344 ∈ [2.24, 3.44] | ✅ dentro |
| fouls | 26.502 ∈ [23.3, 31.4] | ✅ dentro |
| yellow_cards | 5.051 ∈ [2.88, 5.26] | ✅ dentro |
| red_cards | 0.215 ∈ [0.071, 0.54] | ✅ dentro |
| gols ≈ xG (≤10%) | 1.02% | ✅ dentro |
| invalid_matches | 0 | ✅ dentro |
| motm_mismatch | 0 | ✅ dentro |
| subs_over_5 | 0 | ✅ dentro |
| injury_out_of_range | 0 | ✅ dentro |
| rating_out_of_range | 0 | ✅ dentro |
| qualidade monótona | 33.3% → 48.8% → 70.2% → 83.8% → 92.7% | ✅ dentro |
| resultados inesperados possíveis (≥15) | 15: 4.5%, 20: 2.7%; amplo (20% mais desiguais) 17.9% | ✅ dentro |
| posturas moderadas (±35%) | retranca: -22%/-18%, defensiva: -11%/-9%, equilibrada: +0%/+0%, ofensiva: +11%/+10%, ataque_total: +20%/+15% | ✅ dentro |
| posturas monótonas | marcados 0.84 < 0.95 < 1.07 < 1.19 < 1.28; sofridos 0.87 < 0.95 < 1.05 < 1.15 < 1.22 | ✅ dentro |
| inferioridade numérica | sofridos/90 1.19→1.48; marcados/90 1.07→0.73 | ✅ dentro |
| IA: mudanças de postura por time ≤ 4 (máx ≤ 8) | 1.19 (máx 7) | ✅ dentro |

## Métricas monitoradas (sem referência confiável: NÃO validadas)

| Métrica | Valor |
|---|---|
| shots_on_target | 8.957 |
| on_target_pct | 36.604 |
| big_chances | 1.104 |
| corners | 8.512 |
| saves | 6.589 |
| injuries | 0.515 |
| possession_team_sd | 2.299 |
| possession_team_min | 41.000 |
| possession_team_max | 59.300 |
| goals_sd | 1.456 |
| zero_zero_pct | 7.550 |
| five_plus_pct | 8.170 |
| max_goals | 10 |
| administrative | 0 |
| shootouts | 592 |
| posture_changes_per_team | 1.187 |
| posture_changes_max | 7 |
| rating_mean | 6.185 |
| rating_sd | 0.701 |
| rating_lt5_pct | 2.166 |
| rating_ge8_pct | 1.790 |
| rating_min | 2.100 |
| rating_max | 10.000 |

## Qualidade (lote C, campo neutro)

| Diferença de nível | n | Vitória do mais forte | Empate | Vitória do mais fraco | Saldo médio |
|---|---|---|---|---|---|
| 0 | 600 | 33.3% | 32.2% | 34.5% | -0.02 |
| 5 | 600 | 48.8% | 31.5% | 19.7% | +0.61 |
| 10 | 600 | 70.2% | 18.3% | 11.5% | +1.41 |
| 15 | 600 | 83.8% | 11.7% | 4.5% | +2.13 |
| 20 | 600 | 92.7% | 4.7% | 2.7% | +2.88 |

## Posturas (lote B, um lado com postura fixa contra Equilibrada)

| Postura | n | Gols marcados | Sofridos | Δ marcados | Δ sofridos | Faltas |
|---|---|---|---|---|---|---|
| retranca | 1000 | 0.837 | 0.868 | -21.9% | -17.6% | 9.78 |
| defensiva | 1000 | 0.952 | 0.953 | -11.2% | -9.5% | 10.83 |
| equilibrada | 1000 | 1.072 | 1.053 | +0.0% | +0.0% | 11.28 |
| ofensiva | 1000 | 1.187 | 1.154 | +10.7% | +9.6% | 12.28 |
| ataque_total | 1000 | 1.282 | 1.216 | +19.6% | +15.5% | 13.49 |

## Formações (lote D; índice: 0 = 4-3-3, 1 = 4-4-2, 2 = 5-3-2)

| Confronto | n | Gols/jogo | Vitória do lado A |
|---|---|---|---|
| 0x0 | 250 | 2.13 | 36.0% |
| 0x1 | 250 | 2.16 | 31.2% |
| 0x2 | 250 | 2.06 | 36.8% |
| 1x0 | 250 | 2.11 | 35.2% |
| 1x1 | 250 | 2.07 | 30.0% |
| 1x2 | 250 | 2.13 | 34.4% |
| 2x0 | 250 | 2.14 | 36.0% |
| 2x1 | 250 | 2.18 | 41.2% |
| 2x2 | 250 | 2.14 | 33.2% |

## Inferioridade numérica (lote amplo, 1ª expulsão entre 10' e o fim − 10')

1929 partidas com expulsão. Time com 10: marcados/90 1.07 → 0.73; sofridos/90 1.19 → 1.48.

