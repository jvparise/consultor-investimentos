# ADR-011 — Snapshots patrimoniais: Modo B com geração automática na sessão

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O histórico de evolução patrimonial requer snapshots do valor total do portfólio ao longo do tempo. Há dois modos possíveis:

- **Modo A (Calculado):** Sistema multiplica quantidade de cada ativo pelo preço registrado naquela data. Requer preço para cada ativo em cada data do histórico.
- **Modo B (Manual):** Usuário registra o valor total consolidado do patrimônio em uma data. Simples, mas perde o breakdown automático por classe.

## Decisão

**Modo B para o MVP**, com geração automática ao abrir o app:

1. Ao iniciar o app, `SnapshotService.try_auto_snapshot(today)` é chamado
2. Se já existe snapshot para hoje → não faz nada
3. Se não existe → calcula patrimônio atual com base nos preços/valores mais recentes cadastrados
4. Se todos os ativos têm valor atualizado → `SnapshotType.CALCULATED`
5. Se algum ativo está sem preço recente → `SnapshotType.INCOMPLETE` (registra mesmo assim com aviso)
6. Usuário pode sempre inserir um snapshot manual com valor exato

"Automático" significa: gerado na primeira abertura do app no dia, sem ação do usuário. Sem processo em background, sem scheduler — o código só executa quando o app está aberto.

## Alternativas consideradas

**Modo A desde o MVP:** Exigiria que o usuário inserisse preços para cada ativo em cada data histórica — friccão alta de onboarding. Reservado para v2.0.

**Apenas manual, sem geração automática:** Usuário precisaria lembrar de clicar "gerar snapshot" todo dia. Experiência ruim.

## Consequências

**Positivo:**
- Histórico começa a se construir automaticamente desde o primeiro uso
- Usuário não precisa de ação extra para ter evolução patrimonial
- Modo A pode ser adicionado em v2.0 sem quebrar dados existentes

**Negativo:**
- Snapshots do tipo `INCOMPLETE` podem subestimar o patrimônio real se ativos estiverem sem preço atualizado
- O gráfico de histórico é tão rico quanto a frequência de uso do app

**Regra derivada:** O ícone/label `INCOMPLETE` deve ser exibido no gráfico de histórico para snapshots parciais, para que o usuário saiba que o valor pode estar subestimado.
