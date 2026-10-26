# Reestrutura Whitelabel — workspace

Planejamento e acompanhamento do épico que reestrutura o front do portal
(apl-credit-whitelabel). O épico cobre:
- temas de marca em todas as páginas;
- dark mode;
- componentes próprios no lugar do Angular Material;
- a arquitetura `core/shared/layouts/features`.

Aqui ficam as tarefas, as decisões, o design system, as evidências e os
protótipos próprios. O código vive no repositório da empresa, não aqui.

## Repositório pessoal: o que nunca entra

Este repo é pessoal e fica num GitHub pessoal. Antes de qualquer commit,
conferir que nada disto entra:

- **Segredos:** credenciais, tokens de acesso, senhas, chaves e conteúdo de
  `.env`. "Token de design" é outra coisa e pode entrar.
- **Endereços internos:** hosts, URLs e IPs da empresa. Escrever
  `<url-da-sandbox>`, "host da sandbox" etc.
- **Logs:** de build, teste e lint dos repos da empresa.
- **Código da empresa:** código-fonte copiado dos repos, inclusive patches.
  Aqui o código se cita por `arquivo:linha`. Protótipos próprios em
  `anexos/` (prévia, ícones, scripts) são permitidos.
- **Nomes reais:** de pessoas, da empresa, de marcas parceiras, clientes,
  administradoras e fornecedores.
  - Use sempre o **análogo**: "Poliedro" para a empresa e as marcas "Dots",
    "Cerys" e "Viva". Vale também em nomes de arquivo, chaves de tema e
    caminhos citados.
  - A tabela de equivalência não fica no repo.
  - Números e cores podem ficar.
- **Dados de cliente:** CPF, CNPJ e nomes reais. Os da prévia são fictícios.

Conferência rápida antes do commit:

```bash
grep -rniE "password|senha|secret|api[_-]?key|://[^ ]+@|\.io\b|\b10\.[0-9]+\.[0-9]+\.[0-9]+\b|/home/" . --exclude-dir=.git
```

## Valores reais fora do repo

Alguns valores ficam no arquivo local
`~/repos/.reestrutura_whitelabel/privado.md`, fora do controle de versão:
- a URL da sandbox;
- a tabela de nomes reais × análogos;
- onde estão os logs brutos.

Leia esse arquivo quando um documento daqui usar um nome análogo ou um
marcador como `<url-da-sandbox>`. Valor sensível novo vai para lá, e aqui
entra só a referência genérica. Fora deste repo (conversa, repos da
empresa), use os nomes reais.

## Como manter

- **Status:**
  - O README tem a tabela de tarefas e a "Situação" (o que está pronto e o
    que falta).
  - Cada tarefa tem "Status" no topo e "O que foi feito" quando sai do
    papel.
- **Decisões:** decisão tomada vai para `decisoes.md`, com data, quem
  decidiu e o motivo.
- **Validação:** o passo a passo e os números de base ficam em
  `tarefas/roteiro-de-area.md`.
- **Sincronização:** a cada iteração, rode `git pull` antes de mexer. Ao
  terminar, faça commit e `push` direto na `main`.
  - Commits atômicos, em PT-BR, com até 72 caracteres.
  - Prefixo `docs:` ou `chore:`, sem ID de tarefa e sem `Co-Authored-By`.
  - A conferência acima roda antes de cada commit.

As regras de git dos repos da empresa (branch e commit com `TS-…`, sem push
pelo Claude) estão no `CLAUDE.md` da pasta de repositórios e não valem para
este repo.
