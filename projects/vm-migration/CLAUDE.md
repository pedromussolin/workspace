Status: rascunho
Data: 04/11/2026
Tags:

# Migração das telas de operações: regras do projeto

As regras comuns (sigilo, commits, idioma e sincronização) e as regras de trabalho em
`instructions/` estão no `CLAUDE.md` da raiz do repositório. Aqui ficam só as regras específicas deste projeto.

## Análogos deste projeto

Os nomes reais viram análogos, por exemplo "Rafael Frankl" e "Mercato Libero", inclusive em nomes
de arquivo, âncoras e caminhos citados. A máquina é sempre "EC2 de automações", nunca o IP ou o
nome do host.

## Valores reais fora do repo

Hosts, IPs, usuários de banco, credenciais e os nomes reais por trás dos análogos ficam no
arquivo local `~/.config/workspace/private/vm-migration.md`, fora do controle de
versão. Aqui entra só a referência genérica, como "EC2 de automações" ou "usuário de banco
próprio".

## Dados locais fora do repo

Cópias de scripts da EC2, listagens de crontab, logs, dumps de configuração e evidências com dados
reais ficam em `~/.local/share/workspace/projects/vm-migration/`. O código da EC2 é
da empresa: nunca entra no repo, nem em trechos. Aqui entra só a descrição do que ele faz e o
caminho na máquina.

## Como escrever

- Separar o comprovado da hipótese: **[C]** (visto na máquina, no código ou no Datadog) e **[H]**
  (hipótese, com o caminho para validar).
- Cada item do inventário diz quem usa, com que frequência, do que depende e para onde vai.

## Repositórios envolvidos

| Onde | Papel |
|---|---|
| EC2 de automações | origem: telas, rotinas e scripts do Rafael Frankl, fora dos repositórios |
| destino | a definir depois do inventário (D2 de `decisions.md`) |
