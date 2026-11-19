# Interface definitiva e integração geral (Entrega 8)

Implementação do GDD v5.2 §9, §11, §16, §20–§23. Toda ação da interface chama o serviço real. Nenhuma
resposta é simulada no cliente.

## Telas e navegação contextual (GDD §22)

Roteamento por hash (`frontend/src/app/App.tsx`). O menu mostra só as telas que fazem sentido na fase da
sessão (`navItems`):

| Fase da sessão | Menu |
|---|---|
| sem competição | Início · Competição · Dados |
| `setup` / `auction` | Início · Competição · Leilão |
| `squad_completion` | + Leilão (resumo) · Mercado |
| `trading` | Início · Competição · Mercado |
| `competition` | Início · Competição · **Central** · Escalação · Partida |
| `finished` | Início · Competição · Central · Encerramento |

| Rota | Tela |
|---|---|
| `#/session` | Configuração inicial e encerramento/substituição da competição |
| `#/auction` | Leilão: jogadores, temporizador, lances, saldo, oferta ativa, rodadas, resultados laterais, resumo final |
| `#/trading` | Mercado: pesquisa, seleção, elencos, dinheiro opcional, temporizador, aceitar, rejeitar, cancelar, resultados |
| `#/temporada/{central,elenco,calendario,classificacao,estatisticas,resultados}` | Central principal: próximo confronto, meu elenco, calendário, classificação ou chaveamento, estatísticas (4 abas), histórico de partidas |
| `#/escalacao` | Escalação e preparação tática: formação, campo interativo, banco, adequação, indisponíveis, postura inicial, adversário |
| `#/partida` | Partida: placar, relógio, eventos, estatísticas, posturas, velocidade, condição física, substituições, cartões, lesões |
| `#/pos/{match_id}` | Pós-partida: placar, acontecimentos, estatísticas, avaliações, Craque, escalações, tabela atualizada, botão **Próximo confronto** |
| `#/encerramento` | Campeão, campanha do usuário, premiações, campanha dos clubes, histórico completo, nova competição |

## Campo interativo (GDD §9)

`features/season/Pitch.tsx`:
- **Arrastar e soltar** (HTML5) entre vagas, banco e "fora da lista".
- **Toque/clique em dois atletas** troca os dois. Funciona no celular e no teclado, porque cada vaga é um
  botão.
- **Fora da lista** também é destino, para retirar um reserva sem colocar outro no lugar.
- **Indicadores de adequação** por vaga (Natural, Boa, Regular, Improvisado), calculados pelo servidor a
  partir da familiaridade do próprio atleta com a posição. Os limiares de exibição (90/70/40) são
  provisórios (PI-02).
- **Lesionados e suspensos** aparecem com o motivo e não podem entrar. O servidor também recusa
  (`INVALID_LINEUP`).
- A escalação é validada no servidor (`POST /season/lineup`). Ela continua valendo nas rodadas seguintes
  enquanto for válida; se um atleta ficar indisponível, o servidor usa a sugestão automática e explica o
  motivo (`note`).
- A formação fica fixa durante o jogo: depois do início ao vivo, a escalação é bloqueada (`MATCH_IN_PROGRESS`).

## Partida ao vivo (GDD §11, §16)

`services/competition/live.py` (`LiveMatch`) e `POST/GET /season/live*`:
- **Relógio do servidor.** O tempo de jogo é `âncora + tempo real × (96 min nominais ÷ velocidade)`, com
  velocidades de 15 s, 30 s, 60 s ou instantânea. A velocidade pode mudar durante o jogo e só altera essa
  conversão.
- **Não pausa:** desconectar ou recarregar não para o relógio. Ao voltar, a tela continua de onde o servidor
  está (verificado no navegador).
- **Revelação progressiva.** O cliente só recebe eventos com `second ≤ tempo atual`. Não há como ver o
  resultado antes de decidir a postura.
- **Mudança de postura.** Vira um `PostureChange` no tempo de jogo já simulado e vale para as posses
  seguintes.
- **Determinismo.**
  - Ao concluir, `POST /season/play` executa a rodada inteira em paralelo com a mesma tarefa e as decisões
    registradas.
  - A consolidação **compara** a partida do usuário com a apresentação ao vivo (`expect_result`). Qualquer
    divergência impede a consolidação.
  - Testado em todas as velocidades: mesmas decisões = mesmos eventos.
- **Condição física:** só a do próprio time, que é a informação disponível ao técnico. Substituições são
  automáticas (até 5, GDD §13) e aparecem no feed com cartões e lesões.

## Estatísticas (GDD §20)

`GET /season/stats` agrega apenas números produzidos pelo motor (`compute_stats`) e pelo histórico
consolidado. A central tem quatro abas:
- **Classificação ou chaveamento.**
- **Jogadores:** rankings de gols, assistências, média (mínimo de 50%), Craque, jogos e cartões, com filtros
  por clube e por nome.
- **Clubes:** campanha, finalizações, posse média, faltas e cartões.
- **Avançadas:** xG por jogo a favor e contra, saldo de xG, gols − xG, grandes chances, aproveitamento no
  alvo, desarmes, interceptações e defesas.

## Reconexão e versões (GDD §23)

- **Sessão:**
  - o navegador guarda só o ID da sessão;
  - o WebSocket reconecta com espera exponencial;
  - eventos `season.*` recarregam a central (`SessionContext.subscribe` + `useSeason`);
  - respostas antigas são descartadas (contador de sequência);
  - ao terminar a temporada, o cliente ressincroniza a versão da sessão (`competition` → `finished`).
- **Comandos (`useCommand`):**
  - o botão fica desabilitado durante a chamada;
  - repetições automáticas usam a **mesma** `Idempotency-Key`;
  - o servidor devolve a mesma resposta para a mesma chave, então não há comandos duplicados.
- **Sessão perdida:** se o servidor perdeu a sessão, todas as telas mostram "Sua competição não pode mais ser
  recuperada", com o link para iniciar outra (não há salvamento persistente).

## Identidade visual

Tokens de `styles.css` (Entrega 1), derivados do manual oficial: verde-lima `#99FA08`, prata `#F2F2F2`,
cinza `#B8B8B8`, verde-escuro `#033A01`.
- **Tema escuro:** marca oficial sobre preto.
- **Tema claro:** versão secundária, verde-escuro sobre branco.
- **Logotipos:** arquivos oficiais em `frontend/public/brand`.
- **Tipografia:** o manual não define (PI-01); usa a fonte do sistema.
- **Cores fora da marca:** os indicadores de adequação "Boa" e o gramado usam tons de verde funcionais.

## Acessibilidade e responsividade

- Link "Pular para o conteúdo". Ele move o foco sem mudar a rota (bug encontrado no navegador e corrigido).
- Abas com `role="tab"`, botões com `aria-pressed`, medidores de condição com `role="meter"`, tabelas com
  legenda e avisos com `role="alert"`/`status`.
- Telas validadas em 1366×900 e 390×844, nos temas claro e escuro, sem rolagem horizontal.

## Como executar

```bash
.venv/Scripts/python -m services.gateway --port 8000      # API
cd frontend && npm run dev                                 # http://localhost:5173
```

**O leilão real continua bloqueado** até o `AuctionModel` aprovado (fórmulas pendentes). Para demonstrar ou
testar a jornada inteira, há duas opções, ambas **somente para teste**:
- o modelo FALSO dos testes: `SQUADFORCE_AUCTION_MODEL=support.fake_auction_model:FakeAuctionModel` com
  `PYTHONPATH=tests`;
- relógios acelerados: `SQUADFORCE_CLOCK_SCALE=10`.

Nunca use esses valores como regra de jogo.
