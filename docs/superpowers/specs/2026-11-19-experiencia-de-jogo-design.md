# Experiência de jogo — design

Data: 2026-11-19 · Responsável pelas decisões: dono do projeto · Status: aguardando aprovação

## 1. Intenção

O SquadForce funciona, mas "não parece um jogo": é um painel com abas que o jogador precisa navegar.
O objetivo é que ele **jogue**: uma abertura que apresenta o jogo, um botão para começar, e a partir daí
cada fase conduz à seguinte com uma ação principal ("Avançar"), com campo, cartas, placar e torcida.

Diretriz do responsável (2026-11-19): **as novas diretrizes dele prevalecem sobre o GDD v5.2.** Cada regra
alterada é registrada em `docs/game-design/pendencias.md` como decisão do responsável.

### Objetivos
1. Fluxo guiado de jogo, sem menu de abas: Abertura → Nova partida → Tática → Leilão → Mercado → Temporada
   (Central da rodada → Escalação → Jogo ao vivo → Pós-jogo → próxima rodada) → Encerramento.
2. Visual de jogo: estádio noturno, campo desenhado, cartas de jogador, placar estilo telão, transições.
3. Todos os itens pedidos (seção 4).

### Não objetivos
- Motor gráfico (Phaser/Pixi) ou animação da bola em tempo real.
- Mudar fórmulas aprovadas (leilão, motor) além do que está listado aqui.
- Persistência de partidas (continua só em memória).

### Anti-objetivos (seria fracasso mesmo funcionando)
- Voltar a parecer um sistema de gestão (tabelas e abas como navegação principal).
- Quebrar a lógica atual: cliente de API com idempotência, reconexão, relógio do servidor, testes.
- Expor informação oculta (overall, atributos, valor interno, condição do adversário).

## 2. Abordagens consideradas

| | Abordagem | Troca |
|---|---|---|
| **A (escolhida)** | Nova casca de jogo + visual próprio (SVG/CSS) sobre os hooks, cliente e contratos atuais | Mantém lógica e testes; sensação de jogo sem reescrever |
| B | Motor gráfico (Phaser/Pixi) para campo e partida | Animação rica, mas reescreve campo/partida fora do React, difícil de testar |
| C | Biblioteca de componentes (Tailwind/shadcn) | Visual limpo porém "de sistema", migração total de estilos |

O responsável escolheu **A** e delegou criatividade e game design.

## 3. Direção visual — "Noite de estádio"

- **Tema escuro padrão** (já é o padrão do `theme.ts` quando não há preferência salva; passa a ignorar a
  preferência do sistema operacional — só o botão muda para claro). Claro continua disponível.
- Paleta da identidade oficial: preto, verde-lima `#99FA08`, prata. Fundo com gradiente de holofote
  (radial no topo) e textura sutil de gramado nas telas de campo.
- **Tipografia**: títulos condensados em caixa alta (Google Font "Oswald" ou equivalente condensada,
  carregada localmente via `@fontsource` para funcionar offline — decisão do construtor entre as duas),
  números em fonte tabular para placares e dinheiro.
- **Placar estilo telão** (LED): escudos, siglas, placar grande, minuto, posse.
- **Cartas de jogador**: foto (`/api/assets/players/{id}`, silhueta quando não houver), escudo do clube de
  origem, nome, idade, **selo de posição colorido por setor** (GOL laranja, defesa azul, meio verde, ataque
  vermelho). Sem overall (oculto, GDD §6). Cartas do próprio elenco mostram adequação e disponibilidade.
- **Transições**: cada fase abre com um "letreiro" de fase (ex.: "RODADA 7 — SEU JOGO: X × Y"), animação
  curta (≤ 600 ms), respeitando `prefers-reduced-motion`.
- Responsivo: celular a desktop, sem rolagem horizontal.

## 4. Funcionalidades

### 4.1 Fluxo e navegação (substitui o menu de abas)
- **Abertura** (`#/`): logo oficial em destaque, frase do jogo, 3 blocos curtos "Monte no leilão · Negocie ·
  Dispute Liga ou Copa", botão principal **"Nova partida"** (ou **"Continuar"** se houver sessão ativa,
  com resumo da fase). Status dos serviços sai daqui (fica só na área de dados).
- **Barra superior fixa** mínima: logo, fase atual com indicador de etapas (Tática ▸ Leilão ▸ Mercado ▸
  Temporada ▸ Fim), saldo/clube do usuário quando houver, tema, som (liga/desliga), menu "⋯" com
  "Encerrar competição".
- Cada tela tem **uma ação principal** fixa no rodapé (botão grande lima): "Começar leilão", "Ir para o
  mercado", "Ir para a temporada", "Escalar e jogar", "Iniciar partida", "Próxima rodada", etc.
- Na temporada, a **Central da rodada** é a tela base: próximo jogo em destaque, mini-classificação,
  últimos resultados. Elenco, calendário, classificação completa e estatísticas abrem como **painéis
  sobrepostos** (gaveta lateral/tela cheia no celular) a partir de botões da central — não abas.
- O roteamento por hash continua (reconexão e testes e2e), mas a navegação é guiada pela fase.
- Fase muda pelo servidor (WebSocket) → a casca leva o jogador à tela da nova fase com o letreiro.

### 4.2 Nova partida
- Assistente em passos (formato → nº de clubes/turnos → escolher clube), com cartas de escudo grandes para
  o clube. Mesmas validações de `features/session/validation.ts`.

### 4.3 Tática antes do leilão (novo passo)
- Após criar a sessão (fase `setup`), antes de "Começar leilão": o jogador escolhe a formação entre as 11
  oficiais, vendo o desenho no campo.
- Efeito (proposta aceita): vira a **formação inicial da escalação** e orienta o leilão — o painel do
  leilão mostra "vagas da sua formação" por posição (ex.: ZAG 1/2) com o que já comprou.
- Backend: novo campo da sessão `user_formation` (POST `/api/sessions/{id}/formation`, só em `setup`,
  idempotente). A escalação automática do usuário usa essa formação como preferência inicial.
  Bots já escolhem a sua (GDD §10) — sem mudança.

### 4.4 Leilão
- **Ordem das posições**: GOL · LD · ZAG · LE · VOL · ME · ATA em todo o jogo (muda `POSITION_ORDER` no
  backend e frontend; hoje é GOL-LD-LE-ZAG).
- Elencos (seu e dos rivais) agrupados por posição nessa ordem, em colunas com selo colorido; contagem
  por posição.
- Rodada: 5 cartas lado a lado, cronômetro circular grande, saldo e lance máximo sempre visíveis,
  seletor de valor com **− / +** (passos de R$ 100 mil, R$ 500 mil, R$ 1 mi) e "lance mínimo".
- **Redução de lance permitida** (decisão do responsável, sobrepõe GDD §5): qualquer clube pode reduzir o
  próprio lance ativo no mesmo atleta durante a rodada, respeitando lance mínimo e saldo. Repetir o mesmo
  valor continua rejeitado (sem efeito). Desempate por timestamp passa a usar o instante do **valor final**
  (já é assim). Erro `BID_NOT_INCREASED` vira `BID_UNCHANGED`. Bots não mudam de comportamento.
- Resultado da rodada aparece como "carimbo" VENDIDO/SEM LANCE sobre as cartas.

### 4.5 Mercado
- Mesmo visual de cartas, agrupado por posição. Lógica intacta.

### 4.6 Escalação (campinho)
- Campo vertical em SVG com gramado listrado e linhas; cartas compactas (foto, nome, selo, adequação por
  cor de borda, ícones de cartão/lesão).
- **Sem sobreposição**: as vagas são calculadas por linha (GOL/defesa/volantes/meio/ataque) e distribuídas
  com espaçamento igual na largura; cartas ajustam tamanho para caber (mín. 5 por linha). Testado para
  todas as 11 formações em 360 px.
- **Arrastar e soltar** (mouse e toque, Pointer Events; teclado continua com troca por seleção):
  - soltar carta sobre outra carta → troca (titular↔titular, titular↔banco);
  - arrastar uma carta para **outra linha** do campo → o jogo procura a formação oficial cuja contagem por
    linha corresponde ao novo desenho e **troca a formação** automaticamente (aviso "Formação: 4-3-3").
    Se nenhuma oficial corresponder, a carta volta e aparece "Essa formação não é oficial".
  - O seletor de formação continua disponível.

### 4.7 Jogo ao vivo
- Layout: telão no topo; ao centro o **campo tático com as duas equipes** (sua metade de baixo, adversário
  em cima), jogadores como fichas com número/sobrenome, cartões e substituições refletidos; à direita
  (abaixo no celular) **"Outros jogos da rodada"** com placares que mudam no mesmo relógio; embaixo a
  narração de lances e o painel de estatísticas.
- **Estatísticas**: barras comparativas centralizadas (mandante à esquerda, visitante à direita, rótulo no
  meio), alinhadas em grade — posse, finalizações, no alvo, xG, escanteios, faltas, cartões.
- **Pênalti**: lance mostra "Pênalti! Falta de {cometeu} em {sofreu}" (o motor já registra ambos em
  `penalty_awarded`; hoje não há pênalti por mão no motor, então todos mostram autor e vítima).
- **Som da torcida** nos gols (sintetizado com Web Audio: ruído filtrado com envelope de "explosão" + coro
  curto), mais leve para gol do adversário; botão liga/desliga na barra (padrão ligado, lembrado no
  navegador). Também apito no início/fim.
- Postura e velocidade como hoje.
- Backend (`LiveStateOut`, aditivo):
  - `opponent_players`: titulares em campo do adversário (id, nome, posição/vaga, cartões) — informação
    pública (GDD §9); sem condição.
  - `other_matches`: demais partidas da rodada `{match_id, home_club_uid, away_club_uid, score, minute,
    finished}`. São simuladas ao iniciar o ao vivo com a **mesma `FixtureTask`/semente** usada ao jogar a
    rodada (bot × bot, sem decisões do usuário) e reveladas pelo mesmo relógio de jogo: só gols até o
    minuto atual. Na consolidação, o resultado é idêntico (teste).

### 4.8 Pós-jogo e encerramento
- Pós-jogo: telão final, craque da partida em carta destacada, notas, gols — então "Próxima rodada".
- Encerramento: pódio/troféu com campeão, artilheiro, melhor nota.

### 4.9 Desgaste do goleiro (motor)
- Decisão do responsável: goleiros cansam pouco. Novo parâmetro `gk_fatigue_multiplier = 0.35` em
  `params.py` aplicado ao desgaste por minuto e por disputa do goleiro. Depois: rodar
  `homologation_calibration.py` e confirmar que os critérios do motor continuam aprovados (sem mudar limites).

### 4.10 Atualização de dados — área oculta
- Sai da navegação. Rota `#/admin` (não linkada em lugar nenhum). Pede senha; a verificação é **no
  servidor**: POST `/api/admin/login` com a senha → token de sessão de admin em memória (expira ao
  reiniciar). Rotas de importação passam a exigir o token (`X-Admin-Token`). Senha `9153` configurável por
  `SQUADFORCE_ADMIN_PASSWORD` (padrão 9153). A tela mostra importação, catálogo e status dos serviços.
- Link informado ao responsável: `http://localhost:5173/#/admin`.

### 4.11 Status dos serviços (correção)
- `/api/health`: `bot_ai` e `match_engine` deixam de ser `planned` fixos; ficam `ready` (com teste de
  regressão).

## 5. Restrições
- CLAUDE.md: regressão primeiro em bugs; contratos → `export_openapi.py` + `npm run gen:api` +
  `docs/api/contratos.md`; migrações aditivas (aqui nenhuma no SQLite); `Dados/` e `Graphics/` só leitura.
- Mudanças de regra registradas em `pendencias.md`: redução de lance (sobrepõe GDD §5), tática antes do
  leilão para o usuário, desgaste do goleiro, área oculta de dados com senha.
- Suítes completas (pytest, Vitest, e2e, build) verdes antes de declarar pronto; e2e atualizados ao novo fluxo.
- Acessibilidade: tudo acessível por teclado; arrastar tem alternativa por toque/seleção; contraste AA.

## 6. Ordem de entrega (frentes)
1. Backend: health, ordem de posições, redução de lance, formação do usuário, goleiro, admin, `LiveStateOut`.
2. Casca de jogo, abertura, tema, tipografia, cartas, letreiros, som.
3. Nova partida, tática, leilão, mercado.
4. Campinho com arrastar e formação automática; central da rodada e painéis.
5. Jogo ao vivo (campo duplo, outros jogos, estatísticas, pênalti), pós-jogo, encerramento.
6. Testes, e2e, calibração do motor, documentação, executor (rebuild automático já existe).

## 7. Decisões do construtor (Claude)
Paleta e tipografia exatas, desenho das cartas e do campo, efeitos sonoros sintetizados, textos de interface,
multiplicador do goleiro (0,35), passos do seletor de lance, organização em componentes.
