# Calibração estatística — homologação (Entrega 9)

Gerado por `scripts/homologation_calibration.py` (20250 partidas simuladas em 229 s, 10 processos; motor `provisorio-0.6`). Faixas de `criterios.md` (commit `d2cda8e`, anterior a este lote).

Lotes: amplo 10000 (40 clubes REAIS da base, escalação/formação/posturas pela IA, personalidades e situações variadas, 20% eliminatórias) · posturas 5000 · qualidade 3000 · formações 2250.

## Veredito por critério

| Critério | Observado | Resultado |
|---|---|---|
| goals | 2.365 ∈ [2.2, 3.56] | ✅ dentro |
| draw_pct | 25.960 ∈ [22.5, 33.0] | ✅ dentro |
| shots | 24.307 ∈ [22.1, 30.1] | ✅ dentro |
| xg | 2.339 ∈ [2.24, 3.44] | ✅ dentro |
| fouls | 26.670 ∈ [23.3, 31.4] | ✅ dentro |
| yellow_cards | 5.110 ∈ [2.88, 5.26] | ✅ dentro |
| red_cards | 0.218 ∈ [0.071, 0.54] | ✅ dentro |
| gols ≈ xG (≤10%) | 1.10% | ✅ dentro |
| invalid_matches | 0 | ✅ dentro |
| motm_mismatch | 0 | ✅ dentro |
| subs_over_5 | 0 | ✅ dentro |
| injury_out_of_range | 0 | ✅ dentro |
| rating_out_of_range | 0 | ✅ dentro |
| qualidade monótona | 33.2% → 48.8% → 70.0% → 84.0% → 92.7% | ✅ dentro |
| resultados inesperados possíveis (≥15) | 15: 4.5%, 20: 2.7%; amplo (20% mais desiguais) 17.6% | ✅ dentro |
| posturas moderadas (±35%) | retranca: -22%/-18%, defensiva: -11%/-10%, equilibrada: +0%/+0%, ofensiva: +11%/+9%, ataque_total: +20%/+15% | ✅ dentro |
| posturas monótonas | marcados 0.84 < 0.95 < 1.07 < 1.19 < 1.28; sofridos 0.87 < 0.95 < 1.05 < 1.15 < 1.22 | ✅ dentro |
| inferioridade numérica | sofridos/90 1.12→1.56; marcados/90 0.99→0.82 | ✅ dentro |
| IA: mudanças de postura por time ≤ 4 (máx ≤ 8) | 1.17 (máx 7) | ✅ dentro |

## Métricas monitoradas (sem referência confiável: NÃO validadas)

| Métrica | Valor |
|---|---|
| shots_on_target | 8.906 |
| on_target_pct | 36.641 |
| big_chances | 1.104 |
| corners | 8.492 |
| saves | 6.541 |
| injuries | 0.525 |
| possession_team_sd | 2.345 |
| possession_team_min | 41.200 |
| possession_team_max | 58.000 |
| goals_sd | 1.464 |
| zero_zero_pct | 7.670 |
| five_plus_pct | 8.200 |
| max_goals | 10 |
| administrative | 0 |
| shootouts | 591 |
| posture_changes_per_team | 1.172 |
| posture_changes_max | 7 |
| rating_mean | 6.182 |
| rating_sd | 0.698 |
| rating_lt5_pct | 2.216 |
| rating_ge8_pct | 1.722 |
| rating_min | 2.500 |
| rating_max | 10.000 |

## Qualidade (lote C, campo neutro)

| Diferença de nível | n | Vitória do mais forte | Empate | Vitória do mais fraco | Saldo médio |
|---|---|---|---|---|---|
| 0 | 600 | 33.2% | 32.2% | 34.7% | -0.03 |
| 5 | 600 | 48.8% | 31.5% | 19.7% | +0.61 |
| 10 | 600 | 70.0% | 18.5% | 11.5% | +1.41 |
| 15 | 600 | 84.0% | 11.5% | 4.5% | +2.14 |
| 20 | 600 | 92.7% | 4.7% | 2.7% | +2.88 |

## Posturas (lote B, um lado com postura fixa contra Equilibrada)

| Postura | n | Gols marcados | Sofridos | Δ marcados | Δ sofridos | Faltas |
|---|---|---|---|---|---|---|
| retranca | 1000 | 0.837 | 0.868 | -21.9% | -17.6% | 9.78 |
| defensiva | 1000 | 0.951 | 0.952 | -11.3% | -9.6% | 10.83 |
| equilibrada | 1000 | 1.072 | 1.053 | +0.0% | +0.0% | 11.28 |
| ofensiva | 1000 | 1.187 | 1.153 | +10.7% | +9.5% | 12.28 |
| ataque_total | 1000 | 1.282 | 1.216 | +19.6% | +15.5% | 13.49 |

## Formações (lote D; índice: 0 = 4-3-3, 1 = 4-4-2, 2 = 5-3-2)

| Confronto | n | Gols/jogo | Vitória do lado A |
|---|---|---|---|
| 0x0 | 250 | 2.13 | 36.0% |
| 0x1 | 250 | 2.16 | 31.2% |
| 0x2 | 250 | 2.06 | 36.4% |
| 1x0 | 250 | 2.11 | 35.2% |
| 1x1 | 250 | 2.07 | 30.0% |
| 1x2 | 250 | 2.13 | 34.4% |
| 2x0 | 250 | 2.14 | 36.0% |
| 2x1 | 250 | 2.18 | 41.2% |
| 2x2 | 250 | 2.14 | 33.2% |

## Inferioridade numérica (lote amplo, 1ª expulsão entre 10' e o fim − 10')

1965 partidas com expulsão. Time com 10: marcados/90 0.99 → 0.82; sofridos/90 1.12 → 1.56.

