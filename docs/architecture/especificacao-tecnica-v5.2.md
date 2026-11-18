# ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO — GAME DESIGN v5.2

> Transcrição fiel do arquivo `Dados/ESPECIFICAÇÃO TÉCNICA DE IMPLEMENTAÇÃO.docx` (fonte oficial). Em caso de divergência, o .docx original prevalece. Gerado em 2026-11-18 para consulta pelo Claude e pelas Skills.

Projeto: Simulador de Futebol — Leilão, Estratégia e Competições  
Stack aprovada: React + TypeScript, Python + FastAPI, SQLite  
Arquitetura: Serviços especializados separados  
Ambiente de desenvolvimento: Claude no VS Code

## 1. Objetivo

Implementar o Game Design v5.2 respeitando as regras aprovadas para clubes, jogadores, leilão, negociações, motor esportivo, inteligência artificial, Liga, Copa, estatísticas e interface.

A implementação deverá seguir uma sequência modular, com contratos definidos, testes automatizados e critérios rigorosos de aceitação.

O documento integral do Game Design v5.2 será a fonte de referência das regras do jogo.

## 2. Princípios obrigatórios
- Separar os serviços de leilão, inteligência artificial, partidas e competições.
- Utilizar React com TypeScript no frontend.
- Utilizar Python e FastAPI nos serviços.
- Utilizar SQLite para bases persistentes de jogadores e clubes.
- Manter o estado da competição apenas na memória da sessão ativa.
- Não criar salvamentos persistentes, backups ou restauração de competições.
- Garantir operações idempotentes, transações atômicas e relógios autoritativos.
- Simular os confrontos paralelamente, com isolamento por estado inicial da rodada.
- Não considerar um módulo aprovado sem os testes obrigatórios.

## 3. Estrutura do projeto

```text
game-v5.2/
├── .claude/
│   └── skills/
│       ├── game-design-rules/
│       ├── project-architecture/
│       ├── database-import/
│       ├── session-management/
│       ├── auction-system/
│       ├── trading-system/
│       ├── bot-intelligence/
│       ├── match-engine/
│       ├── competition-system/
│       ├── frontend-ui/
│       └── testing-validation/
│
├── frontend/
│   └── src/
│       ├── app/
│       ├── pages/
│       ├── components/
│       ├── features/
│       ├── api/
│       ├── hooks/
│       └── types/
│
├── services/
│   ├── gateway/
│   ├── session/
│   ├── data/
│   ├── auction/
│   ├── trading/
│   ├── bot_ai/
│   ├── match_engine/
│   └── competition/
│
├── shared/
│   └── python/
│       ├── contracts/
│       ├── domain/
│       └── errors/
│
├── database/
│   └── migrations/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contracts/
│   ├── simulation/
│   └── end_to_end/
│
├── docs/
│   ├── game-design/
│   ├── architecture/
│   └── api/
│
└── README.md
```

Cada pasta em .claude/skills/ deverá conter um arquivo SKILL.md, com instruções específicas para o Claude. Utilize também as skills adicionadas na pasta Game, importe-as para o projeto

## 4. Criação obrigatória das Skills

A criação das Skills será parte da primeira entrega do projeto, juntamente com a infraestrutura e os contratos iniciais.

As Skills não substituirão o Game Design. Elas funcionarão como guias especializados para consultar e aplicar suas regras.

Skills previstas

| Skill | Responsabilidade |
|---|---|
| game-design-rules | Preservar as regras aprovadas do Game Design v5.2 e identificar decisões ainda pendentes |
| project-architecture | Orientar organização dos serviços FastAPI, contratos, comunicação e padrões de código |
| database-import | Implementar validação de Excel, SQLite, transações e rollback |
| session-management | Gerenciar estado temporário, reconexão, transições e encerramento de sessões |
| auction-system | Orientar lances, relógios, orçamento, contratações e complementação de elencos |
| trading-system | Orientar propostas, trocas atômicas, limites e negociação entre bots |
| bot-intelligence | Orientar decisões de contratação, escalação, formações e posturas dos bots |
| match-engine | Preservar regras de atributos, eventos, xG, gols, notas, lesões e substituições |
| competition-system | Implementar Liga, Copa, calendários, chaveamentos e processamento paralelo |
| frontend-ui | Orientar React, TypeScript, responsividade, navegação contextual e interação |
| testing-validation | Definir testes obrigatórios, determinismo, calibração estatística e critérios de aceitação |

Padrão obrigatório de uma Skill

Cada SKILL.md deverá conter:
- Nome e descrição da especialidade.
- Situações em que o Claude deverá utilizar a Skill.
- Regras aprovadas do Game Design aplicáveis ao módulo.
- Responsabilidades e limites do módulo.
- Contratos e dependências relevantes.
- Orientações de implementação.
- Erros e comportamentos proibidos.
- Testes e critérios de aceitação.
- Referências à documentação detalhada.

As Skills deverão ser objetivas e reutilizáveis. Regras extensas permanecerão nos documentos de referência para evitar duplicação desnecessária.

Exemplo de Skill

Arquivo: .claude/skills/auction-system/SKILL.md

---

name: auction-system

description: Implementar e revisar o leilão de jogadores, incluindo ofertas, concorrência, orçamento, relógios, seleção de atletas e complementação dos elencos.

---

O conteúdo da Skill deverá orientar o Claude a:
- Consultar as regras oficiais do leilão no Game Design v5.2.
- Preservar o orçamento inicial de R$ 120 milhões.
- Trabalhar com cinco jogadores da mesma posição por rodada.
- Utilizar relógios controlados pelo servidor.
- Garantir ofertas sigilosas e um lance ativo por clube.
- Aplicar corretamente o desempate por tempo e ordem de aceitação.
- Impedir saldo negativo e duplicação de contratações.
- Garantir elencos finais com exatamente 18 jogadores contratados.
- Criar e executar os testes obrigatórios.

Regra fundamental: nenhuma Skill poderá inventar novas regras de jogo ou alterar decisões aprovadas sem autorização.

## 5. Ordem obrigatória de preparação

Antes de implementar funcionalidades complexas:
- Preparar o repositório e a estrutura de diretórios.
- Disponibilizar o Game Design v5.2 como documentação de referência.
- Criar as 11 Skills previstas.
- Verificar nomes, descrições, referências e instruções.
- Definir os contratos técnicos dos serviços.
- Inicializar frontend, backend e SQLite.
- Implementar importações Excel com validação e rollback.
- Implementar o gerenciamento inicial de sessão.
- Criar e executar os testes da primeira entrega.

As Skills dos módulos futuros poderão ser refinadas à medida que os contratos forem detalhados, sem alterar as regras já aprovadas.

## 6. Contratos técnicos iniciais

A comunicação utilizará:
- HTTP REST para consultas, importações e comandos.
- WebSocket para atualizações de tempo, ofertas, propostas e eventos ao vivo.
- Contratos tipados para comunicação interna entre serviços.

Endpoints iniciais previstos:

| Método | Endpoint |
|---|---|
| GET | /api/health |
| GET | /api/catalog/clubs |
| GET | /api/catalog/players |
| POST | /api/imports/players |
| POST | /api/imports/clubs |
| POST | /api/sessions |
| GET | /api/sessions/{id} |
| POST | /api/sessions/{id}/close |
| GET | /api/competitions/options |

Cada operação que modifica estado deverá possuir identificador, validação e proteção contra duplicação.

## 7. Primeira entrega — Infraestrutura, Skills e dados

Escopo:
- Estrutura inicial do projeto.
- React + TypeScript funcionando.
- Serviços FastAPI organizados.
- Criação das 11 Skills do projeto.
- Documentação das regras e contratos.
- SQLite com estrutura de bases persistentes.
- Importação de jogadores e clubes.
- Validação e substituição transacional das bases.
- Gerenciamento inicial de sessões temporárias.
- Bloqueio de importações durante competições ativas.
- Testes automatizados.

Não implementar ainda o leilão completo, o mercado de negociações ou o motor esportivo.

## 8. Critérios de aceitação da primeira entrega

A entrega somente será aprovada quando:
- A aplicação inicializar corretamente.
- Frontend e backend conseguirem se comunicar.
- Os serviços possuírem responsabilidades e contratos definidos.
- As 11 Skills estiverem criadas, organizadas e com instruções coerentes com o Game Design.
- As referências das Skills apontarem para documentos existentes.
- O SQLite aceitar bases válidas.
- Importações inválidas preservarem as bases anteriores.
- Os dados dos jogadores e clubes forem validados.
- Sessões puderem ser criadas e encerradas em memória.
- Importações forem bloqueadas durante uma competição ativa.
- Testes obrigatórios passarem.
- Não existirem falhas críticas ou importantes pendentes.

## 9. Orientações obrigatórias para o Claude

Antes de desenvolver cada módulo:
- Consultar a Skill correspondente.
- Ler as seções aplicáveis do Game Design v5.2.
- Verificar dependências e contratos existentes.
- Identificar possíveis inconsistências.
- Implementar somente o escopo previsto.
- Criar testes automatizados.
- Executar os testes e corrigir falhas.
- Registrar as alterações realizadas.

Não declarar funcionalidades concluídas sem evidência verificável.

As Skills deverão ser mantidas junto ao código, de forma que alterações técnicas relevantes sejam refletidas na documentação correspondente.

Resultado esperado: uma primeira entrega funcional, com infraestrutura inicial, serviços organizados, Skills especializadas, SQLite, importações seguras e gerenciamento de sessões, pronta para receber os módulos esportivos e financeiros nas fases seguintes.
