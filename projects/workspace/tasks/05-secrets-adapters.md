Status: a fazer (mapeada para depois)
Data: 08/11/2026
Tags: segredos, credenciais, adaptadores

# 05 — Segredos por adaptador: cofres de mercado e o modelo local como reserva

## Contexto

Pedido do usuário em 08/11/2026, no redesenho do produto como assistente do dev com núcleo
hexagonal (portas e adaptadores). O dev escolhe onde guarda os segredos: ferramentas de mercado,
como o 1Password ou os segredos e ambientes do repo no GitHub, entram como adaptadores da porta de
credenciais. Quem não usa nenhuma fica com um modelo local, como o de hoje
(`~/.config/workspace/credentials`, lido só pelo `ws`). Tarefa registrada para depois; o texto
será melhorado antes da spec.

## Desenho combinado (a detalhar numa spec própria)

- Porta de credenciais no núcleo: pede um segredo pelo nome (`jira.token`, `github.token`) e nunca
  lista valores; o núcleo não sabe de onde ele vem.
- A config escolhe os adaptadores de cada espaço (empresa, cliente ou pessoal) numa ordem de
  procura, por exemplo: 1Password, depois o chaveiro do sistema, depois o arquivo local.
- Adaptadores candidatos: 1Password (CLI `op`, referências `op://cofre/item/campo`), GitHub
  (segredos de repo e de ambiente), chaveiro do sistema (keyring), arquivo local com permissão 600
  (o modelo de hoje).
- O valor nunca passa pelo agente de IA, pelo chat nem por variável exportada no shell: o `ws`
  busca na hora e entrega direto ao cliente HTTP.

## A fazer antes de implementar

- Conferir o que o GitHub permite. Pela documentação, o valor de um segredo do repo não pode ser
  lido de volta pela API, só usado dentro do Actions. Se for assim, o GitHub serve como destino
  (gravar o segredo para o CI) ou para rodar dentro do Actions, não como fonte na máquina do dev.
- Escolher o modelo local de reserva: o arquivo de hoje, o chaveiro do sistema ou um arquivo
  cifrado.
- Ver como cada adaptador pede desbloqueio (biometria do 1Password, senha do chaveiro) sem travar
  o agente.
- Cada espaço com o seu cofre: segredo de uma empresa nunca serve em outra.

## Pronto quando

- Trocar o adaptador no config muda a origem dos segredos sem mexer em nenhum comando.
- Sem nenhum cofre configurado, o modelo local funciona como hoje.
- Nenhum valor de segredo aparece em log, chat, arquivo do repo ou variável exportada.
