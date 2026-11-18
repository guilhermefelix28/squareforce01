# GAME DESIGN DOCUMENT — VERSÃO 5.2

> Transcrição fiel do arquivo `Dados/GAME DESIGN DOCUMENT — VERSÃO 5.2.docx` (fonte oficial). Em caso de divergência, o .docx original prevalece. Gerado em 2026-11-18 para consulta pelo Claude e pelas Skills.

Projeto: Simulador de Futebol — Leilão, Estratégia e Competições  
Estado: Consolidação das regras aprovadas  
Objetivo: Referência funcional para a implementação da aplicação web

## 1. VISÃO GERAL

O jogo será um simulador de futebol para um usuário, competindo contra clubes controlados por inteligência artificial.

O ciclo principal será:
- Configurar a competição e escolher um clube.
- Participar do leilão de jogadores.
- Completar automaticamente os elencos.
- Participar do mercado de negociações.
- Preparar escalações e estratégias.
- Disputar Liga ou Copa contra bots.
- Consultar resultados, estatísticas e histórico.
- Conhecer o campeão e as premiações.

A aplicação será web, responsiva para computadores e celulares, com temas claro e escuro.

## 2. CLUBES E PARTICIPANTES
- Catálogo de 40 clubes selecionáveis: 20 da Série A e 20 da Série B.
- O clube escolhido pelo usuário deverá participar da competição, sem duplicação.
- A Liga poderá ter qualquer quantidade inteira de clubes entre 2 e 20.
- Na seleção da Liga, os clubes da Série A terão prioridade, seguidos pelos da Série B, respeitada a inclusão obrigatória do clube do usuário.
- A Copa admitirá 2, 4, 8, 16 ou 32 participantes.
- Os participantes da Copa serão sorteados entre os clubes elegíveis, sem repetição.
- Rankings internos dos clubes e características privadas dos bots permanecerão ocultos.
- Escudos serão localizados por seus identificadores. Na ausência de imagem, a interface utilizará ícone padrão com as iniciais do clube.

## 3. BASE DE JOGADORES E POSIÇÕES

A base será importada de planilhas Excel (jogadores.xlsx) para SQLite, preservando todos os jogadores válidos definidos na base utilizada pelo projeto, inclusive reservas e jovens.

Posições exibidas na interface:

| Exibição | Código interno |
|---|---|
| GOL | GK |
| LD | DR |
| LE | DL |
| ZAG | DC |
| VOL | DM |
| ME | MC |
| ATA | STC |

O simulador utilizará atributos inspirados no Football Manager, com ponderações específicas para cada posição, familiaridade posicional e contribuição coletiva.

A adequação posicional deverá produzir impacto esportivo proporcional, com penalidade máxima de até 35% conforme a regra já definida.

O overall não será utilizado isoladamente para calcular o rendimento real de um jogador escalado.

## 4. ORÇAMENTO E VALORES

Cada clube começará com R$ 120 milhões.

Regras econômicas:
- O mercado poderá trabalhar com valor máximo de referência de R$ 50 milhões por jogador.
- O lance mínimo de leilão poderá atingir até R$ 30 milhões.
- Valor de mercado calculado a partir do overall calibrado e da idade.
- Potencial, versatilidade e prestígio do clube não entram diretamente no cálculo do valor de mercado.
- A mediana-alvo de overall será 70, e notas superiores a 90 deverão ser relativamente raras.
- As fórmulas econômicas propostas dependerão de calibração e validação sobre a base definitiva.

## 5. LEILÃO DE JOGADORES

O leilão terá rodadas de dez segundos, cada uma apresentando cinco jogadores de uma mesma posição principal.

Funcionamento:
- Ofertas fechadas e sigilosas.
- Um lance ativo por clube em cada rodada.
- Possibilidade de aumentar o lance ou mudar o alvo, respeitando as validações.
- Proibição de reduzir o lance vigente sobre o mesmo jogador.
- Se a troca de alvo falhar, o lance anterior permanecerá válido.
- Vencedor definido pelo maior lance válido.
- Em igualdade, vencerá quem atingiu o valor final primeiro, pelo timestamp do servidor.
- Se os timestamps forem exatamente iguais, será utilizada a ordem sequencial de aceitação do servidor.
- Nenhuma contratação poderá gerar saldo negativo ou jogador duplicado.
- Os clubes deverão preservar ao menos R$ 500 mil por vaga restante em seu elenco.

Duração global:

| Competição | Clubes | Tempo |
|---|---|---|
| Liga | 2 a 10 | 10 minutos |
| Liga | 11 a 20 | 15 minutos |
| Copa | 2, 4 ou 8 | 10 minutos |
| Copa | 16 | 15 minutos |
| Copa | 32 | 20 minutos |

O leilão terminará antecipadamente se todos os clubes alcançarem os 18 jogadores.

A sequência das posições será definida por sorteio ponderado, considerando necessidades coletivas, disponibilidade, histórico recente e aleatoriedade controlada. Uma posição elegível deverá aparecer ao menos uma vez em uma janela de 14 rodadas concluídas, desde que existam pelo menos cinco jogadores elegíveis distintos.

A seleção dos cinco jogadores deverá apresentar variedade de qualidade, evitar repetição excessiva de não vendidos e excluir atletas já adquiridos.

Na interface do leilão:
- Exibir identificação, foto quando disponível, idade, clube, posição, lance mínimo, saldo e oferta ativa.
- Ocultar overall, atributos, valor de mercado interno e ofertas adversárias.
- Oferecer digitação manual do valor.
- Botões rápidos: lance mínimo, acréscimos de R$ 100 mil, R$ 500 mil e R$ 1 milhão.
- Confirmar operação e apresentar retorno imediato.
- Mostrar resultado da rodada em painel lateral sem interromper o relógio global.

## 6. INTELIGÊNCIA DOS BOTS NO LEILÃO

Quatro personalidades ocultas:
- Agressivo.
- Conservador.
- Equilibrado.
- Oportunista.

Todas utilizarão a mesma capacidade de avaliação esportiva, diferenciando principalmente tolerância ao risco e comportamento estratégico.

O cálculo de ganho esportivo marginal observará:
- 80% da mudança na qualidade dos 11 titulares.
- 20% da mudança na qualidade dos sete reservas.

Preço, saldo, necessidades posicionais e oportunidades futuras serão considerados separadamente.

Os bots deverão:
- Otimizar o elenco como conjunto, considerando formações e familiaridade.
- Utilizar limites estratégicos dinâmicos para ofertas.
- Considerar concorrência com base apenas em informações públicas.
- Preservar recursos para completar o elenco.
- Reavaliar ofertas durante a rodada quando justificável.
- Aumentar gradualmente a urgência perto do encerramento, sem desespero artificial.
- Não consultar ofertas secretas dos adversários.

## 7. COMPLEMENTAÇÃO AUTOMÁTICA DOS ELENCOS

Cada clube deverá terminar a etapa de montagem com exatamente 18 jogadores contratados: 11 titulares e sete reservas.

Haverá duas reservas de atletas, distintas dos jogadores já vendidos:

Reserva básica: quantidade suficiente para completar todos os elencos, com atletas predominantemente simples, preços de até R$ 500 mil por vaga e distribuição protegida.

Reserva complementar: atletas intermediários e alguns destaques, organizados conforme a quantidade de clubes, posições e qualidade disponível.

Regras de complementação:
- Aquisição complementar ao preço médio entre valor de mercado e lance mínimo.
- Para cada clube, limite de melhorias complementares igual a mínimo(18 − C, piso(C / 4)), em que C representa suas contratações efetivas no leilão.
- No máximo um atleta de destaque entre as melhorias complementares de cada clube.
- Destaque definido como jogador com overall calibrado no percentil 85 ou superior da base completa.
- O limite será recalculado quando a base de jogadores for substituída.
- Distribuição coletiva justa, sem prioridade arbitrária de processamento entre clubes.
- Preservação de exclusividade, orçamento e composição dos elencos.
- Nenhuma compensação artificial por mau desempenho no leilão.

Após a complementação, o jogo apresentará o resumo dos elencos e saldos.

## 8. MERCADO DE NEGOCIAÇÕES

O mercado começará exclusivamente quando o usuário clicar em Iniciar negociações.

Duração global: três minutos, sem pausa.

Regras:
- Trocas de um jogador por outro.
- Possibilidade de pagamento adicional somente pelo clube proponente.
- Até três negociações concluídas por clube.
- Uma proposta ativa por clube.
- Prazo máximo de dez segundos por proposta, ou até o término do mercado, se ocorrer antes.
- Sem contrapropostas.
- Cancelamento permitido ao proponente enquanto a proposta estiver pendente.
- Transações atômicas: jogadores e eventual dinheiro trocam simultaneamente.
- Elenco sempre com 18 jogadores contratados.
- Nenhuma operação poderá criar duplicação ou saldo negativo.

Usuário e bots poderão iniciar propostas, inclusive bots negociando entre si.

Os bots avaliarão ganho esportivo, adequação, orçamento, necessidades posicionais e personalidade. Poderão aceitar pequenas perdas esportivas quando existir justificativa financeira ou estratégica suficiente.

A interface permitirá pesquisar atletas por nome, clube e posição. Propostas recebidas aparecerão em painel lateral com contagem regressiva.

## 9. ESCALAÇÃO E PREPARAÇÃO

Antes de cada partida, o usuário poderá:
- Consultar informações públicas do próximo adversário.
- Ver resultados, estatísticas, formações anteriores e jogadores de destaque.
- Escolher a formação.
- Organizar os 11 titulares e até sete reservas disponíveis.
- Posicionar livremente os atletas, inclusive fora de suas posições naturais.
- Consultar indicadores visuais de adequação.
- Selecionar a postura inicial.

O campo interativo permitirá arrastar jogadores e, em dispositivos móveis, trocar dois atletas por seleção.

Lesionados e suspensos não poderão ser escalados enquanto indisponíveis.

Se um clube tiver menos de 11 jogadores aptos antes da partida, receberá atletas emergenciais genéricos, temporários, gratuitos e de baixa qualidade apenas para completar os titulares. Esses atletas não integrarão o elenco contratado.

## 10. MOTOR ESPORTIVO

As partidas serão simuladas progressivamente, por acontecimentos encadeados.

Exemplo de fluxo esportivo:

Possessão → construção → oposição defensiva → oportunidade → finalização → intervenção do goleiro → resultado do lance.

O placar não será predeterminado.

O modelo utilizará:
- Atributos efetivos dos atletas.
- Adequação posicional.
- Formação escolhida.
- Postura tática.
- Condição física.
- Contexto esportivo.
- Aleatoriedade controlada.

Serão possíveis resultados inesperados, empates, partidas sem gols e goleadas ocasionais.

O motor deverá ser calibrado por grandes quantidades de partidas, com referências estatísticas do futebol real.

## 11. POSTURAS TÁTICAS

Cinco posturas:
- Retranca.
- Defensiva.
- Equilibrada.
- Ofensiva.
- Ataque Total.

As posturas alterarão moderadamente criação ofensiva, exposição defensiva, comportamento coletivo e desgaste.

Não concederão gols garantidos nem substituirão a importância dos atributos dos jogadores.

Durante a partida, a formação permanecerá fixa. O usuário poderá modificar a postura tática, e os bots poderão alterá-la conforme sua avaliação estratégica.

As mudanças afetarão somente eventos ainda não simulados.

## 12. FINALIZAÇÕES, GRANDES CHANCES E xG

O xG será contextual e independente da execução individual.

Seu cálculo considerará características como:
- Distância e ângulo.
- Tipo de oportunidade.
- Pressão defensiva.
- Posição do jogador.
- Contexto do chute.

Os atributos do finalizador e do goleiro modificarão separadamente a probabilidade efetiva de gol, sem dupla contagem.

Grandes chances serão identificadas pelo xG contextual combinado com características favoráveis do lance, com parâmetros calibrados estatisticamente.

As intervenções dos goleiros considerarão reflexos, posicionamento, capacidade em situações de um contra um e demais atributos relevantes.

## 13. FALTAS, CARTÕES, LESÕES E DESGASTE

Faltas, cartões e lesões serão gerados de forma contextual e probabilística, associados aos eventos esportivos.

Serão considerados atributos, tipo de disputa, intensidade, condição física e contexto tático.

As lesões poderão gerar afastamentos de zero a três partidas.
- Lesões serão cumpridas nas próximas partidas oficiais do clube, independentemente de Liga ou Copa.
- Cartões e suspensões disciplinares serão controlados separadamente por competição.
- Folgas não contarão como cumprimento de afastamentos.
- Jogadores não lesionados recuperarão integralmente a condição física antes de cada nova partida.
- O desgaste não se acumulará entre confrontos, apenas durante o jogo.

Até cinco substituições automáticas por equipe poderão ocorrer conforme lesões, desgaste, rendimento, adequação e situação da partida.

Expulsos não poderão retornar nem ser substituídos diretamente.

Se uma equipe ficar com menos de sete jogadores durante o confronto, haverá encerramento imediato, com derrota administrativa por 3 × 0 ou preservação do placar mais favorável ao adversário. Resultado oficial e estatísticas esportivas serão registrados separadamente.

## 14. NOTAS INDIVIDUAIS E CRAQUE DA PARTIDA

Notas de 0,0 a 10,0, exibidas com uma casa decimal.

As avaliações serão contextuais por posição, considerando:
- Qualidade, dificuldade e importância das ações.
- Eventos positivos e negativos.
- Tempo em campo.
- Contribuição real para a partida.

O overall natural não determinará diretamente a nota.

O Craque da Partida será o atleta com maior avaliação contextual. Empates na nota exibida serão resolvidos pela maior precisão interna; persistindo, será utilizado o impacto das ações decisivas.

## 15. INTELIGÊNCIA DOS BOTS NAS PARTIDAS

Os bots poderão adaptar suas formações antes de cada confronto, usando a formação escolhida antes do leilão como referência.

Durante o jogo, a formação ficará fixa.

As decisões táticas considerarão:
- Placar e tempo restante.
- Força efetiva dos jogadores.
- Estatísticas e eventos observados.
- Condição física e desvantagem numérica.
- Classificação da Liga ou risco de eliminação na Copa.
- Personalidade moderada e oculta.

Os bots utilizarão um modelo probabilístico leve para estimar consequências de vitória, empate e derrota sob diferentes posturas.

Haverá reavaliações periódicas e outras provocadas por eventos relevantes. Mudanças exigirão ganho estratégico suficiente, com intervalo de estabilidade e exceções para acontecimentos decisivos.

Não haverá acesso a eventos futuros ou a resultados de outros jogos da mesma rodada.

## 16. VELOCIDADES E DETERMINISMO

Velocidades de apresentação:
- 15 segundos.
- 30 segundos.
- 60 segundos.
- Instantâneo.

Todas utilizarão o mesmo motor esportivo.

Cada partida terá sementes pseudoaleatórias automáticas. Estado inicial, versão, parâmetros, semente e sequência de decisões idênticos deverão reproduzir exatamente os acontecimentos.

A velocidade visual não poderá alterar os resultados quando as decisões forem equivalentes.

O usuário não precisará configurar sementes.

## 17. LIGA

A Liga terá de 2 a 20 clubes, em qualquer quantidade inteira.

Antes do leilão, o usuário escolherá:
- Turno único.
- Turno e returno.

O calendário utilizará um algoritmo de confrontos todos contra todos, sem duplicações indevidas, com distribuição equilibrada dos mandos.

Em quantidade ímpar de participantes, cada rodada terá um clube de folga, sem registrar partida ou reduzir afastamentos indevidamente.

A classificação será atualizada após o fechamento completo das rodadas.

## 18. COPA

A Copa admitirá 2, 4, 8, 16 ou 32 clubes.

O torneio será disputado em chave eliminatória com:
- Sorteio dos participantes elegíveis.
- Uma partida por confronto.
- 90 minutos regulamentares.
- Disputa de pênaltis em caso de empate.
- Ausência de prorrogação.
- Avanço automático do vencedor à próxima fase.

Pênaltis serão registrados separadamente, sem acrescentar gols à artilharia dos 90 minutos.

Se o clube do usuário for eliminado, a competição continuará até a final, com avanço de fase controlado pelo usuário.

## 19. PARTIDAS PARALELAS

As partidas da mesma rodada ou fase serão processadas em paralelo.

Cada confronto receberá um estado competitivo inicial imutável, com a classificação e as condições oficiais do começo da rodada.

Os jogos evoluirão independentemente, sem acesso aos eventos ou resultados de outros confrontos simultâneos.

Somente após todas as partidas terminarem e passarem nas validações o sistema consolidará resultados, classificação, estatísticas, lesões e suspensões.

Falhas críticas impedirão consolidação parcial.

## 20. ESTATÍSTICAS E HISTÓRICO

Haverá uma central com quatro abas:
- Classificação.
- Jogadores.
- Clubes.
- Estatísticas avançadas.

Os rankings incluirão gols, assistências, notas, prêmios de Craque da Partida e outros indicadores produzidos pelo motor.

Para o ranking de média de notas, o jogador precisará ter participado de pelo menos 50% das partidas disputadas por sua própria equipe, arredondado para cima.

Todas as partidas concluídas, inclusive entre bots, terão histórico completo de eventos, estatísticas, escalações, posturas observáveis e avaliações.

Dados internos privados dos bots continuarão ocultos.

## 21. PÓS-PARTIDA E ENCERRAMENTO

A tela pós-partida será completa, com:
- Placar e principais acontecimentos.
- Estatísticas do confronto.
- Avaliações individuais.
- Craque da Partida.
- Classificação ou chaveamento atualizado.
- Botão manual Próximo confronto.

Não haverá avanço automático.

Ao concluir a Liga ou Copa, o sistema apresentará campeão, campanha do usuário, rankings e premiações finais.

## 22. INTERFACE E NAVEGAÇÃO

A interface terá uma central principal de gerenciamento, com acesso contextual a elenco, calendário, classificação, estatísticas e histórico.

Leilão, mercado de negociações e partidas possuirão telas específicas.

O aplicativo será responsivo e suportará temas claro e escuro.

## 23. ESTADO DA SESSÃO

Uma única competição ativa por sessão.

Encerrar a sessão ou iniciar outra competição com progresso a perder exigirá confirmação.

Não haverá salvamento persistente, backup ou restauração de competições.

A reconexão automática será permitida enquanto o estado temporário continuar ativo na memória do servidor.

Relógios do leilão e do mercado não serão pausados por desconexões individuais.

## 24. EXCEL, SQLITE E IMPORTAÇÕES

As planilhas originais serão selecionadas pelo usuário e importadas diretamente para SQLite, sem cópias permanentes dos arquivos Excel.

Importações deverão:
- Validar estrutura, valores e identificadores.
- Substituir somente a base correspondente.
- Utilizar transações.
- Preservar dados existentes em caso de erro crítico.
- Não criar backups ou sistemas de versionamento.

Novas importações serão bloqueadas enquanto existir competição ativa.

## 25. ARQUITETURA TÉCNICA

A aplicação utilizará serviços especializados, com separação das responsabilidades de:
- Leilão.
- Inteligência artificial.
- Motor de partidas.
- Competições.

Negociações, estatísticas e gerenciamento de sessão terão componentes próprios conforme a implementação.

Os serviços deverão oferecer operações idempotentes, relógios autoritativos, validações centrais, controle de concorrência e sincronização de estados.

O SQLite persistirá as bases importadas; o progresso da competição permanecerá temporário.

## 26. CRITÉRIOS DE ACEITAÇÃO

O jogo somente será considerado pronto quando:
- Todos os testes funcionais obrigatórios forem aprovados.
- Não houver falhas críticas pendentes.
- Não houver falhas importantes pendentes.
- As regras financeiras e esportivas forem respeitadas.
- O determinismo for comprovado.
- Os resultados estatísticos estiverem adequadamente calibrados.
- A inteligência dos bots apresentar comportamento coerente.
- Os requisitos de desempenho forem atingidos.
- A execução paralela e a integração entre serviços forem validadas.

Somente pendências exclusivamente cosméticas, documentadas, poderão permanecer.

Fim da consolidação funcional do Game Design v5.2.

Este documento representa a especificação de design. Sua aprovação não significa que os módulos já foram implementados ou que seus testes foram executados.
