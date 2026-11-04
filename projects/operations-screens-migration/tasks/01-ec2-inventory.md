# 01 — Inventário da EC2 de automações

Status: a começar (05/11/2026)

## Objetivo

Listar tudo o que roda na EC2 de automações do Rafael Frankl e dar um destino a cada item. É a
base para quebrar os dois projetos em tarefas:

- telas, rotinas e ferramentas do time de operações → este projeto;
- liquidação do Mercato Libero → Artemis V2, tarefa 13
  (`projects/artemis-v2/tasks/13-mercato-libero-settlement.md`);
- o resto → registrado aqui como "fora do escopo por enquanto", para não se perder.

O inventário é um só, porque as duas frentes estão na mesma máquina. Cópias de scripts, crontab
e configuração ficam na pasta local do projeto (ver `CLAUDE.md`), nunca no repo.

## O que levantar

- [ ] Data de saída do Rafael e até quando a máquina e os acessos dele valem (D3).
- [ ] Sessão de passagem com o Rafael: pedir que mostre cada tela e rotina rodando.
- [ ] Agendamentos: crontab (agenda de tarefas do Linux), timers do systemd, serviços no ar.
- [ ] Telas: o que serve cada uma, como o time acessa (endereço, rede, login) e quem usa.
- [ ] Scripts e rotinas: linguagem, onde está o código (está em algum git?), dependências.
- [ ] Integrações: APIs da empresa chamadas, banco (o usuário de banco próprio lê e grava direto
      no Postgres da cessão), S3, e-mail, arquivos de entrada e saída.
- [ ] Credenciais e segredos usados (só a lista do que existe; valores nunca vão para o repo).
- [ ] O que acontece se cada item parar: quem percebe e em quanto tempo.

## Inventário

| # | Item | Tipo (tela, rotina, script) | Quem usa | Frequência | Depende de | Destino | Status |
|---|---|---|---|---|---|---|---|

## Fontes

- Datadog, 22/10 a 04/11/2026: chamadas da máquina à cessão, já resumidas em
  `projects/artemis-v2/evidence/mercato-libero-ec2-calls-2026-11-04.md`. Mostra só o que passa
  pela API da cessão; o que vai direto ao banco ou a outros sistemas não aparece ali.
