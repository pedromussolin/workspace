+++
card = "TS-5706"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-16
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 01 — Inventário da EC2 de automações

Status: inventário preenchido (16/11/2026); destinos propostos, à espera da D2 (Pietro Nett)

## Resumo

- **153 itens** na EC2 de automações: 127 vivos e 26 apagados do repositório. Os vivos são 14 de
  infraestrutura, 30 do Mercato Pago, 27 de clientes e áreas, 19 de Bluedeck, Compliance e
  Simplix e 37 telas dos dois portais [C, código no `9c2d10b` e READMEs de 05/11 e 09/11].
- **Cada item tem um destino proposto.** A decisão é a D2, do Pietro. A proposta segue regras
  fixas: relatório e aviso por e-mail vão para o envio de relatórios; escrita na liquidação vai
  para a Artemis V2; telas usadas vão para o portal whitelabel; jobs que só leem e avisam vão
  para o agendador do apl-shared-service; tela escondida desde 04/11 que ninguém reclamou é
  desligada, depois de confirmar com a área.
- **Nada fica na VM** (T19, 16/11): cada item migra ou é desligado.
- **50 itens já têm cartão:** 26 no envio de relatórios (TS-5704), 16 no épico TS-5705
  (liquidação do Mercato Pago), 7 na chegada dos dados do Mercato Pago (TS-5775) e 1 no Service
  Report (TS-5625). Os 25 scripts de envio de relatórios cabem nos cards que já existem (T20).
- **44 itens não têm cartão:**
  - 4 envios fora dos 25 da TS-5717: estoque mensal ao Mercato Pago, parcelas zeradas da Omnis e
    as duas ingestões de CCB do OCR;
  - 7 jobs para o apl-shared-service;
  - 8 telas para o whitelabel;
  - 19 itens em dois projetos novos por área: Tesouraria (fluxo de caixa, Padtek e Simplix) e
    Compliance (covenants);
  - 6 famílias de ferramentas manuais do Bluedeck, ainda sem lugar nem dono fora da VM.
- **Os outros 59 itens:** 23 para desligar, 29 que não migram e 7 ações da passagem da VM.

## Antes da saída do Rafael

Achados que valem independentemente do destino de cada item:

1. **Os alarmes caem na caixa pessoal do Rafael [C].** O aviso de falha de todos os scripts
   (`mv_lib/mail.py:114-119`) tem o endereço dele fixo no código, e mais 20 arquivos o usam como
   destinatário ou cópia. Quando a caixa for desativada, toda falha passa calada. Trocar por uma
   lista do time é a primeira mudança (IN04). Dono: TS-5565.
2. **Ele é o titular de todas as credenciais [C].** São 48 variáveis em texto puro no registro
   do Windows. Há também senhas antigas em dois commits do histórico, chaves de acesso ao S3 no
   código de dois scripts do OCR apagados em 05/11 e a credencial do Bluedeck num script apagado.
   Tratar tudo como comprometido e rotacionar (IN10).
3. **Contas pessoais fazendo papel de conta de serviço.** O usuário do SFTP dos ganhos semanais
   da VLTS I é dele [C] (CL11). O usuário da API do Bluedeck talvez também seja [H]: confirmar com
   ele.
4. **Estado que só existe no disco da VM [C].** Estão fora do git:
   - as duas chaves dos SFTPs;
   - a linha de base dos monitores de cadastro do Bluedeck;
   - a foto anterior do reprocessamento do Mercato Pago;
   - o analítico diário;
   - o modelo do Jurídico;
   - os scripts de operação da máquina.
   Copiar antes de desligar (IN11, IN12).
5. **A cópia da VM pode não ser o HEAD [C].** O deploy é por cópia direta sobre a pasta servida.
   Na passagem, comparar a cópia da VM com o `9c2d10b` (IN13).
6. **Riscos do portal de Operações enquanto ele estiver no ar** (registrados, não corrigidos) [C]:
   - o segredo que assina o login está fixo no código;
   - o "esqueci a senha" troca a senha de qualquer conta sem login;
   - a tela Automações deixa qualquer usuário logado editar o caminho de um job e executá-lo;
   - 9 rotas não pedem autenticação;
   - o portal de incidentes (8506) não tem login.

## Acoplamentos que pesam no plano

- **Analítico diário do P2.** A TS-5775 desliga o P1–P5, e com eles o analítico que o P2 grava
  na VM. A TS-5727 deixa de depender dele: o esperado do dia passa a ser calculado direto dos
  File 4 do SFTP, por regra nomeada (TS-5712). Ainda dependem do analítico [C] a autocorreção
  (TS-5753), o monitor de liquidações da Tesouraria (PT25) e o e-mail de conferência dos File 4.
- **Covenants.** O portal importa funções dos processadores de covenants [C]. Os jobs e as telas
  de Compliance precisam mudar juntos (BD13 a BD17, PT03, PT04 e PT23).
- **Telas com dado congelado.** Os carregadores da tela Acompanhamento de Fundos e da tabela de
  cadastro de fundos da CVM foram apagados em 05/11 e 09/11 [C]. A tela continua no ar com dado
  parado e sem alarme (PT05).
- **12 telas com o menu escondido desde 04 e 05/11** [C, `Projetos/0. Front/.claude/CLAUDE.md`].
  Os endpoints seguem no ar, e o portal não registra acesso. A proposta de desligar essas telas
  depende de cada área confirmar que não as usa.
- **Fechamento de lotes.** A agenda de 09/11 tem só os disparos das 17:00 e das 20:45; os das
  16h e das 18h estão inativos [C, `Mercato_Libero/README.md:55-58`]. O comentário do código e o
  levantamento da Artemis (13-automations-survey) ainda falam em 4 disparos por dia.
- **Sem banco de teste [C].** Toda execução escreve em produção, e não há teste automatizado.
  Cada migração roda em paralelo com o script e compara a saída antes de desligá-lo.

## Objetivo

Listar tudo o que roda na EC2 de automações do Rafael Frankl e dar um destino a cada item. O
inventário é um só para as duas frentes da mesma máquina: as telas, rotinas e ferramentas do
time de operações ficam neste projeto, e a liquidação do Mercato Libero vai para a Artemis V2
(tarefa 13, do sistema em diante). O resto fica registrado aqui, para não se perder.

## O que foi levantado

- [ ] Data de saída do Rafael e até quando a máquina e os acessos dele valem (D3).
- [ ] Sessão de passagem com o Rafael (TS-5565): pedir que mostre cada tela e rotina rodando.
- [x] Agendamentos: o orquestrador (laço que lê a agenda no Redshift) e três tarefas do Windows.
      Não há crontab nem systemd: a máquina é Windows. A agenda real fica para conferir (ver
      "Fontes").
- [x] Telas: 37 linhas, entre telas no ar, telas escondidas e rotas mortas, nos portais 8510 e
      8506.
- [x] Scripts e rotinas: Python 3.11, código no repositório de automações (deploy por cópia),
      biblioteca comum `mv_lib`.
- [x] Integrações: Redshift, réplica da cessão, register, banco do OCR, API da cessão, datawall,
      private-credit, S3, SFTP, SharePoint, Bluedeck, GalaPay, CVM, ANBIMA, B3, BCB, Azure
      OpenAI, SMTP. Nenhum script grava direto no Postgres da cessão [C].
- [x] Credenciais: a lista de grupos está no IN10; os valores nunca entram aqui.
- [x] O que acontece se cada item parar: está no detalhe local de cada item (campo "se parar");
      os casos graves estão nas duas seções acima.

## Inventário

Uma linha por script, tela ou grupo de ferramentas parecidas. Prefixos: IN infraestrutura, MP
Mercato Pago, CL clientes e áreas, BD Bluedeck, Compliance e Simplix, PT telas.

- **Frequência:** dos READMEs (05/11 e 09/11) e de comentários no código; o "id" é a linha da
  agenda. "?" quando nenhum documento diz.
- **Depende de:** só os sistemas; tabelas, variáveis e caminhos estão no detalhe local.
- **Destino proposto:** a proposta para a D2. "[H]" quando depende de algo ainda não confirmado.
- **Status:** "ativo" e "no ar" estão no HEAD e na agenda de 05/11 ou 09/11; não foram medidos na
  máquina.

### IN — Infraestrutura, agenda e credenciais

| # | Item | Tipo | Quem usa | Frequência | Depende de | Destino proposto | Status |
|---|---|---|---|---|---|---|---|
| IN01 | Orquestrador (agendador das automações) | infra | todas as automações agendadas | contínuo | Redshift, Postgres local, disco da VM, registro do Windows | desligar depois do último job | ativo |
| IN02 | Agenda dos jobs | infra | orquestrador | lida a cada 5 min | Redshift | passagem: fica até o último job sair | ativo |
| IN03 | Biblioteca comum mv_lib | biblioteca | 54 scripts e os 2 portais | — | registro do Windows, driver ODBC | não migra como biblioteca: cada função tem equivalente no destino (data-lake-api para… | ativo |
| IN04 | Alarme de falha das automações | infra | Rafael | a cada falha | SMTP | ação imediata: trocar por uma lista do time antes da saída do Rafael | ativo |
| IN05 | Histórico de execuções (Postgres local) | infra | tela Monitor da MV do portal | a cada execução | — | passagem: exportar antes de desligar a VM | ativo |
| IN06 | Tarefa 'Fronts - Reset' | infra | os dois portais | diária 04:00 + logon | registro do Windows | desligar junto com os portais | ativo |
| IN07 | Tarefa 'Fronts - Monitor memoria' | infra | diagnóstico | horária | — | desligar junto com a VM | ativo |
| IN08 | Tarefa 'Orquestrador - Watchdog' | infra | orquestrador | periódica | — | desligar junto com o orquestrador | ativo |
| IN09 | nginx e rotas dos portais | infra | usuários dos portais | contínuo | — | desligar junto com os portais | ativo |
| IN10 | Credenciais (48 variáveis) | credencial | todas as automações e portais | — | — | passagem: rotacionar todas (TS-5565) | ativo |
| IN11 | Chaves privadas dos SFTPs | credencial | P1 e estornos do MP | diária | SFTP | passagem: guardar no cofre do destino e liberar o IP novo nos SFTPs | ativo |
| IN12 | Pastas de trabalho e estado em disco | infra | ~30 scripts e o portal | — | — | passagem: copiar para fora da VM antes de desligá-la (monitores do Bluedeck, fotos do… | ativo |
| IN13 | Repositório e ambiente Python | infra | — | — | — | passagem: congelar e conferir a cópia da VM contra o HEAD 9c2d10b | ativo |
| IN14 | SMTP com usuário e senha | integração | todos os scripts de e-mail | — | — | envio de relatórios: e-mail pelo Graph do apl-shared-service (TS-5715) | ativo |

### MP — Liquidação, alertas e e-mails do Mercato Pago (`Mercato_Libero/`)

| # | Item | Tipo | Quem usa | Frequência | Depende de | Destino proposto | Status |
|---|---|---|---|---|---|---|---|
| MP01 | P1 Download dos File 4 | agendado | lista 3 da mv_mail_list | 07:30 todo dia, fim de semana incluído | Redshift, SFTP, chave SFTP, SMTP, disco da VM | chegada dos dados (TS-5775) | ativo |
| MP02 | P2 Tratamento + analítico diário | agendado | interno: alimenta P3–P5, a autocorreção, os e-mails das 9h às 11h20… | 07:45 todo dia | SMTP, disco da VM | chegada dos dados (TS-5775) | ativo |
| MP03 | P3 Upload de cancelamentos | agendado | interno, sem e-mail | 08:00 todo dia | API da cessão, datawall, disco da VM | chegada dos dados (TS-5775) | ativo |
| MP04 | P4 Upload de baixas parciais | agendado | interno, sem e-mail | 08:10 todo dia | API da cessão, datawall, disco da VM | chegada dos dados (TS-5775) | ativo |
| MP05 | P5 Upload de baixas totais | agendado | interno, sem e-mail | 08:45 todo dia | API da cessão, datawall, disco da VM | chegada dos dados (TS-5775) | ativo |
| MP06 | P* Autocorreção do upload | agendado | tesouraria e autor | 10:00 em dia útil | réplica da cessão, API da cessão, datawall, Redshift, SMTP, disco da VM | Artemis V2 (TS-5753) | ativo |
| MP07 | P6 Baixa de parcelas zeradas | agendado | lista 21 | 16:00 em dia útil | API da cessão, datawall, Redshift, SMTP, disco da VM | Artemis V2 (TS-5755) | ativo |
| MP08 | P8 Cancelamentos incompletos (baixa forçada) | agendado | lista 21 | 16:30 todo dia | réplica da cessão, API da cessão, datawall, Redshift, SMTP, disco da VM | Artemis V2 (TS-5754) | ativo |
| MP09 | P7 Fechamento de lotes | agendado | tesouraria e autor | 17:00 e 20:45 em dia útil | réplica da cessão, API da cessão, SMTP | Artemis V2 (TS-5738) | ativo |
| MP10 | PATCH do padrão de liquidação (ajuste_produtos_mp) | agendado | embutido em P3, P4, P5, P*, P6, P8, PPV, Tool CTT e na tela de baixa… | a cada execução de quem o chama | API da cessão | desligar (TS-5750) | ativo |
| MP11 | Cancelamento extraordinário de PPV | agendado | lista 15 | quinta 10:00 | réplica da cessão, API da cessão, datawall, Redshift, S3, SFTP, SMTP, disco da VM | chegada dos dados do MP (TS-5775): incluir o arquivo de PPV, hoje fora da TS-5775 [H] | ativo |
| MP12 | Upload do estoque mensal ao MP | agendado | cliente externo, pela área do SFTP [H] | 5º dia útil, 15:00 | Redshift, S3, SFTP, SMTP | envio de relatórios, onda nova: data-lake-api para o S3 do cliente (sem cartão) | ativo |
| MP13 | Destravar pagamentos presos em 'apto' | sob demanda (portal) | tesouraria | manual, sem linha na agenda | réplica da cessão, API da cessão, datawall, SMTP, disco da VM | Artemis V2 (TS-5752) | ativo |
| MP14 | Monitor de divergências cessão x Lake (monitor do ETL) | agendado | lista 39 | 10:00 em dia útil | réplica da cessão, Redshift, SMTP, disco da VM | épico TS-5705: alertas do MP (TS-5751) | ativo |
| MP15 | Checagem de reprocessamento do estoque | agendado | lista 18 | 11:00 em dia útil | Redshift, SMTP, disco da VM | épico TS-5705: alertas do MP (TS-5751) | ativo |
| MP16 | Checagem de impairment | agendado | lista 17 | 11:15 em dia útil | Redshift, SMTP, disco da VM | épico TS-5705: alertas do MP (TS-5751) | ativo |
| MP17 | Alerta de write-off não feito | agendado | lista 19 inteira [H] | 1º dia útil, 14:00 | Redshift, SMTP | épico TS-5705: alertas do MP (TS-5751) | ativo |
| MP18 | Alerta de write-off pendente | agendado | lista 19 inteira [H] | último dia útil, às 14h, 16h, 18h e 20h | Redshift, SMTP | épico TS-5705: alertas do MP (TS-5751) | ativo |
| MP19 | E-mails 'Valores processados' e 'Liquidações rejeitadas' (MP-1) | agendado | lista 2 | 17:30 em dia útil | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5725) | ativo |
| MP20 | E-mail 'Resultado do processamento diário' | agendado | interno | 9h, 9h30, 10h, 10h30 e 11h em dia útil | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5727): esperado calculado dos File 4 (TS-5712), sem a planilha… | ativo |
| MP21 | E-mail 'Valor conciliado' ao MeLib | agendado | cliente externo Mercato Pago/MeLib + interno | 11:20 em dia útil | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5727): esperado calculado dos File 4 (TS-5712), sem a planilha… | ativo |
| MP22 | Parcial diária de retirada de recusados | agendado | lista 11 | 18:00 todo dia | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5725): rota de liquidação, rejeitados por motivo | ativo |
| MP23 | Retirada semanal de recusados CITTI/NPL (BGT) | agendado | externos: administrador BGT e MeLib | segunda 05:00 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5725): rota de liquidação, rejeitados por motivo | ativo |
| MP24 | Retirada semanal de recusados NP (Fynvest) | agendado | externos: administrador Fynvest e MeLib | segunda 05:00 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5725): rota de liquidação, rejeitados por motivo | ativo |
| MP25 | Estornos mensais (valores negativos) | agendado | cliente externo MeLib | dia 25, 14:00 | Redshift, SFTP, chave SFTP, SMTP, disco da VM | envio de relatórios (TS-5741): regra nomeada sobre os File 4 do SFTP (TS-5712) | ativo |
| MP26 | Aviso de write-off mensal | agendado | administrador BGT e interno | dia 25, 15:00 | Redshift, SMTP | envio de relatórios (TS-5741): posição de ativos com regra nomeada (TS-5712) | ativo |
| MP27 | Baixa contábil por contrato (planilha) | ferramenta manual | operação ou tesouraria, a pedido do MeLib [H] | manual, sem agenda | API da cessão, datawall, Redshift, disco da VM | desligar: a tela de baixa massiva faz o mesmo e vai para a Artemis V2 (TS-5705) | ativo |
| MP28 | Baixa contábil por parcela (planilha) | ferramenta manual | operação ou tesouraria, a pedido do MeLib [H] | manual, sem agenda | datawall, Redshift, disco da VM | Artemis V2 (TS-5705): baixa por parcela na mesma tela de baixa massiva [H] | ativo |
| MP29 | Destravar aptos (versão antiga) | ferramenta manual | ninguém deveria usar | manual, sem agenda | réplica da cessão, API da cessão, datawall, disco da VM, driver ODBC | desligar: apagar (substituído pelo destravar aptos atual) | ? |
| MP30 | Extração trimestral da carteira CITTI | ferramenta manual | pedido pontual [H] | manual, sem agenda | Redshift, disco da VM | desligar: pedido pontual [H] | ? |

### CL — Relatórios e rotinas por cliente e área

| # | Item | Tipo | Quem usa | Frequência | Depende de | Destino proposto | Status |
|---|---|---|---|---|---|---|---|
| CL01 | FIDC FBRX3: base de operações e estoque | agendado | Cliente externo | dia útil 08:30, id 116 | Redshift, SMTP, disco da VM | envio de relatórios (TS-5740): data-lake-api, posição de ativos | ativo |
| CL02 | FIDC Fornecedores: cessões diárias | agendado | Cliente externo | dia útil 00:01, id 121 | réplica da cessão, Redshift, SMTP, disco da VM, driver ODBC | envio de relatórios (TS-5724): platform-cessao, rota de contratos | ativo |
| CL03 | FIDC Fornecedores: cessões mensais | agendado | Cliente externo | dia 1, 00:01, id 122 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): platform-cessao, rota de contratos | ativo |
| CL04 | FIDC Fornecedores: valores a pagar (cobrança) | agendado | Cliente externo e a conciliação, que fecha o lote | dia útil 05:00, id 113 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): rota de contratos com filtro por vencimento | ativo |
| CL05 | FIDC Fornecedores: pendura a acrescer | agendado | Lista 35 | dia útil 05:00, id 123 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): platform-cessao, rota de contratos + regra de fee | ativo |
| CL06 | FIDC Fornecedores: fee mensal | agendado | Cliente externo | dia 1, 05:00, id 120 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): rota de liquidação por mês, com a regra de fee | ativo |
| CL07 | FIDC Fornecedores: vencimentos atualizados | agendado | Listas 38 e 39 | segunda 07:00, id 124 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): platform-cessao, rota de contratos | ativo |
| CL08 | FIDC Vektor: relação de baixas semanal | agendado | Cliente externo | segunda 14:00, id 142 | réplica da cessão, Redshift, SMTP, disco da VM | envio de relatórios (TS-5725): platform-cessao, rota de liquidação | ativo |
| CL09 | FIDC VLTS I: projeção de valor presente | agendado | Lista 25 | dia útil 12:00, id 135 | Redshift, SMTP | envio de relatórios (TS-5741): data-lake-api + regra de cálculo | ativo |
| CL10 | FIDC VLTS I: estoque diário | agendado | Cliente externo Voltis, lista 23 | dia útil 17:00, id 134 | Redshift, SMTP, disco da VM | envio de relatórios (TS-5740): data-lake-api, posição de ativos | ativo |
| CL11 | FIDC VLTS I: ganhos semanais (pedido de transferência) | agendado | Cliente Voltis [H] | segunda 05:05, id 136 | réplica da cessão, Redshift, SFTP, chave SFTP, SMTP, disco da VM | envio de relatórios (TS-5741): arquivo do SFTP com regra que valida na cessão | ativo |
| CL12 | FIDC Fornecedores: download de lastros | agendado | Time de Cadastro | dia útil 11:00, 11:30, 12:00, 12:30 e 13:00, ids 111 e… | réplica da cessão, private-credit, SharePoint, disco da VM | apl-shared-service: job agendado (private-credit para o SharePoint pelo Graph) [H] | ativo |
| CL13 | FIDC Fornecedores: termos de cessão assinados | agendado | Lista 40 e time de Cadastro | dia útil 16:05, id 112 | réplica da cessão, Redshift, register, SFTP, chave SFTP, SMTP, SharePoint, disco da VM | apl-shared-service: job agendado (SFTP com chave para o SharePoint e e-mail) [H] | ativo |
| CL14 | Equimedix FIDC (adm. Dayvale): renegociações e régua de PDD | agendado | Controladoria | dia útil 17:00, id 163 | Redshift, SMTP | envio de relatórios (TS-5741): data-lake-api + regra em código | ativo |
| CL15 | Middle Office: amortizações programadas | agendado | Middle Office | dia útil 09:00, id 139 | Redshift, SMTP, Bluedeck, disco da VM | apl-shared-service: job agendado (Bluedeck e e-mail), junto com os monitores do Bluedeck | ativo |
| CL16 | FIDCs Omnis: parcelas zeradas | agendado | Lista 45 | segunda 15:00, id 162 | Redshift, SMTP, disco da VM | envio de relatórios, onda nova: data-lake-api (sem cartão) | ativo |
| CL17 | FIDC Padtek: boletos pagos | agendado | Lista 29 e Conciliação/Operações | dia útil 06:00, id 84 | Redshift, SMTP, GalaPay, SharePoint, disco da VM | envio de relatórios (TS-5741): conexão GalaPay (TS-5707) e cópia no SharePoint (TS-5715) | ativo |
| CL18 | FIDC Padtek: boletos mensais (emissão e envio) | biblioteca do portal | Tesouraria | sob demanda por botão desde 09/11 | Redshift, SMTP, GalaPay, registro do Windows | projeto novo: Tesouraria no whitelabel (Padtek, emissão) | ativo |
| CL19 | FIDC Padtek: motor de fluxo das operações | biblioteca do portal | Tesouraria | sob demanda pelo portal | Redshift | projeto novo: Tesouraria no whitelabel (Padtek) | ativo |
| CL20 | PLGN: relação de fundos ativos (CVM) | agendado | Lista 37 | 1º dia útil do mês 09:00, id 143 | Redshift, SMTP, CVM, disco da VM | envio de relatórios (TS-5741): download da CVM (TS-5707) com regra nomeada | ativo |
| CL21 | Jurídico: cobrança mensal do controle processual aos escritórios | agendado | Escritórios de advocacia externos | dia 27, 09:00, id 109 | Redshift, SMTP, disco da VM | envio de relatórios (TS-5724): anexo fixo no S3 para a lista, em cópia oculta | ativo |
| CL22 | Tesouraria: projeção de fluxo de caixa dos fundos | agendado | Tesouraria/Riscos | dia útil 13:00, id 80 | Redshift, CVM | projeto novo: Tesouraria no whitelabel (fluxo de caixa: job e tela juntos, baseline antes) | ativo |
| CL23 | Tesouraria: troca do caixa inicial | agendado | Tesouraria | dia útil 18:00, id 159 | Redshift | projeto novo: Tesouraria no whitelabel (fluxo de caixa) | ativo |
| CL24 | Tesouraria: alerta de fluxos de caixa negativos | agendado | Riscos, com cópia para o Rafael, os dois fixos no código | dia útil 16:00, id 150 | Redshift, SMTP, disco da VM | projeto novo: Tesouraria no whitelabel (fluxo de caixa) | ativo |
| CL25 | OCR: ingestão de CCBs do Simplix | agendado | Serviço de OCR e, por ele, a Monitoria de Lastros do portal [H] | dia útil 16:00, id 114 | Redshift, S3, SMTP | envio de relatórios (report-transfer S3 para S3, já existe) ou job no apl-shared-service… | ativo |
| CL26 | OCR: ingestão de CCBs do Voltis Supply (SFTP do parceiro) | agendado | Serviço de OCR [H] | dia útil 09:45, id 110 | S3, SFTP, SMTP | envio de relatórios (report-transfer SFTP para S3, já existe) ou job no… | ativo |
| CL27 | OCR: report de processamento | agendado | Lista 20 | dia útil 09:00, id 73 | Redshift, banco do OCR, SMTP, disco da VM | envio de relatórios (TS-5740): consulta do OCR no data-lake-api (TS-5743) | ativo |

### BD — Bluedeck, Compliance e Simplix

| # | Item | Tipo | Quem usa | Frequência | Depende de | Destino proposto | Status |
|---|---|---|---|---|---|---|---|
| BD01 | Monitor diário do cadastro de instrumentos (Bluedeck) | agendado | lista de e-mail 48 | dia útil 09:00, id 165 | Redshift, SMTP, Bluedeck, disco da VM | apl-shared-service: job agendado | ativo |
| BD02 | Monitor diário do cadastro de carteiras (Bluedeck) | agendado | lista de e-mail 48, a mesma do monitor de instrumentos | dia útil 09:15, id 168 | Redshift, SMTP, Bluedeck, disco da VM | apl-shared-service: job agendado | ativo |
| BD03 | Alerta de carteiras sem eventos futuros | agendado | Middle, cópia ao autor | 1º dia útil da semana 10:00, id 158 | Redshift, SMTP, Bluedeck | apl-shared-service: job agendado | ativo |
| BD04 | Pendências de cadastro de fundos (CVM × Bluedeck) | agendado | Middle, cópia ao autor | dia útil 14:00, id 154 | SMTP, Bluedeck, CVM, registro do Windows | apl-shared-service: job agendado | ativo |
| BD05 | Ferramentas Bluedeck: extração e diagnóstico (10) | ferramenta manual | quem cuida do cadastro no Bluedeck | manual | Bluedeck, ANBIMA, disco da VM | a decidir: lugar e dono das ferramentas manuais fora da VM | ativo |
| BD06 | Ferramentas Bluedeck: padronização de nomes (2) | ferramenta manual | cadastro/middle [H] | manual | disco da VM | a decidir: lugar e dono das ferramentas manuais fora da VM | ativo |
| BD07 | Ferramentas Bluedeck: escrita em instrumentos (9) | ferramenta manual | cadastro/middle sob demanda | manual | Bluedeck, disco da VM | a decidir: lugar e dono das ferramentas manuais fora da VM | ativo |
| BD08 | Ferramentas Bluedeck: escrita em carteiras e fundos (4) | ferramenta manual | cadastro/middle sob demanda [H] | manual | Bluedeck, disco da VM | a decidir: lugar e dono das ferramentas manuais fora da VM | ativo |
| BD09 | Aprovação em massa de cotas (NAVPS) | ferramenta manual | autor, carga pontual [H] | manual | Bluedeck | não migra: carga única de 08/05/2026 | ? |
| BD10 | Ferramentas Bluedeck: participantes e investidores (3) | ferramenta manual | cadastro/middle, cargas pontuais [H] | manual | Bluedeck, disco da VM | a decidir: lugar e dono das ferramentas manuais fora da VM | ? |
| BD11 | Ferramentas Bluedeck: estrutura de campos customizados (6) | ferramenta manual | autor [H] | manual | Bluedeck | a decidir: lugar e dono das ferramentas manuais fora da VM | ? |
| BD12 | Ferramentas Bluedeck: legado e cargas únicas (9) | ferramenta manual | autor, na migração do cadastro | manual | Bluedeck, disco da VM | não migra: serviram a uma migração que já terminou | ? |
| BD13 | Processador de covenants: padrão | agendado | Compliance e Riscos | dia útil 16:30, id 161, com o rótulo 'Específicos' na agenda | Redshift, SMTP, Bluedeck | projeto novo: Compliance no whitelabel (jobs no apl-shared-service e telas), se… | ativo |
| BD14 | Processador de covenants: específicos | agendado | Compliance e Riscos | dia útil 16:30, id 145, com o rótulo 'Padrão' na agenda | Redshift, SMTP, Bluedeck | projeto novo: Compliance no whitelabel (vai com o processador padrão) | ativo |
| BD15 | PL dos fundos via Bluedeck (módulo) | biblioteca do portal | os dois processadores de covenants e o módulo de compliance do portal | a cada execução dos processadores | Bluedeck | projeto novo: Compliance no whitelabel (vai com os covenants) | ativo |
| BD16 | Alarme diário de covenants | agendado | lista de e-mail 41 | dia útil 17:30, id 147 | Redshift, SMTP | projeto novo: Compliance no whitelabel (vai com os processadores) | ativo |
| BD17 | Avanço da apuração dos covenants globais | agendado | Compliance | nenhuma: nunca agendado | portal 8510, registro do Windows | projeto novo: Compliance no whitelabel (vira tarefa do backend) | nunca agendado |
| BD18 | Simplix: separador do relatório de repasses | biblioteca do portal | Tesouraria | sob demanda pela tela | portal 8510, disco da VM | projeto novo: Tesouraria no whitelabel (Simplix: motor e tela juntos) | ativo |
| BD19 | Simplix: gerador do CNAB 444 | biblioteca do portal | Tesouraria | sob demanda pela tela, depois do separador | Redshift, portal 8510 | projeto novo: Tesouraria no whitelabel (Simplix: motor e tela juntos) | ativo |

### PT — Telas dos portais

| # | Item | Tipo | Quem usa | Frequência | Depende de | Destino proposto | Status |
|---|---|---|---|---|---|---|---|
| PT01 | Login, sessão e 'Esqueci/Trocar senha' (shell) | tela | todos os usuários do portal 8510 | diário | Redshift, SMTP | portal whitelabel: usa a autenticação dele | no ar |
| PT02 | Administração | tela | admin | sob demanda | Redshift, SMTP | portal whitelabel: usa a gestão de usuários dele | no ar |
| PT03 | Compliance › Covenants Automáticos | tela | Compliance | ? | Redshift, CVM, Azure OpenAI | projeto novo: Compliance no whitelabel, se Compliance confirmar o uso (menu oculto desde… | no ar |
| PT04 | Compliance › Covenants Globais (inclui Monitor de Globais) | tela | monitor: responsáveis de Riscos, Automação, Produtos, Gestão, Legal,… | diário | Redshift, CVM, Azure OpenAI | projeto novo: Compliance no whitelabel, se Compliance e Riscos confirmarem a conferência… | no ar |
| PT05 | Controladoria › Acompanhamento de Fundos | tela | Controladoria | ? | Redshift | desligar (dado congelado desde a última carga), salvo se a Controladoria pedir a carga… | no ar |
| PT06 | Formalização › Monitoria de lastros | tela | Formalização | ? | Redshift, banco do OCR, S3 | portal whitelabel (módulo Formalização), leitura pelo data-lake-api | no ar |
| PT07 | Formalização › Rastrear CCBs MP | tela | Formalização | sob demanda | Redshift, S3 | portal whitelabel (módulo Formalização) | no ar |
| PT08 | Formalização › Dots · Conferência e Dots · Acervo | tela | Formalização | ? | banco do OCR, S3 | desligar depois de exportar o acervo (lote fechado) | no ar |
| PT09 | Middle › Bluedeck › Arquivo de movimentações | tela | Middle | ? | — | portal whitelabel (módulo Middle): conversor simples, sem integração | no ar |
| PT10 | Middle › Bluedeck: Aprovação de cotas, Reabertura de cotas, Eventos Corporativos (Fundos… | tela | Middle | ? | Bluedeck | desligar (confirmar com Middle) | no ar |
| PT11 | Middle › Calendário | tela | Middle | ? | Redshift | desligar (confirmar com Middle) | no ar |
| PT12 | Middle › Ferramentas de IA | tela | Middle | ? | CVM, Azure OpenAI | desligar (confirmar com Middle) | no ar |
| PT13 | Middle › Fundos e Cotas | tela | Middle | ? | Redshift | desligar: nenhum script do repo lê a tabela | no ar |
| PT14 | Middle › Mercato Pago › Service Report | tela | Middle | mensal | Redshift, S3, disco da VM | TS-5625 (whitelabel, Módulos › Middle › Relatórios MP) | no ar |
| PT15 | Middle › Rastreador ANBIMA | tela | Middle | ? | ANBIMA | desligar (confirmar com Middle) | no ar |
| PT16 | Operações › Incidentes operacionais (8510) | tela | role operacoes | sob demanda | Redshift | portal whitelabel: um módulo de incidentes só, unificando as duas tabelas | no ar |
| PT17 | Projetos › Automações | tela | Projetos/Automação | sob demanda | Redshift | desligar com o orquestrador | no ar |
| PT18 | Projetos › Mailing | tela | Projetos/Automação | sob demanda | Redshift, SMTP | envio de relatórios (TS-5723): listas viram contatos no shared | no ar |
| PT19 | Projetos › Monitor da MV | tela | Projetos/Automação | ? | Postgres local | desligar com o orquestrador | no ar |
| PT20 | Projetos › Monitor da Máquina (painel de processos) | tela | Projetos/Automação | ? | portal 8510, disco da VM | desligar com a VM | no ar |
| PT21 | Projetos › Pipeline | tela | Projetos | ? | Redshift | desligar: tracker pessoal, o Jira cobre | no ar |
| PT22 | Riscos › Bluedeck (Monitor de transações) | tela | Riscos | diário [H] | Redshift, Bluedeck | portal whitelabel (módulo Riscos) | no ar |
| PT23 | Riscos › Controle de covenants | tela | Riscos | ? | Redshift | projeto novo: Compliance no whitelabel (vai com os covenants) | no ar |
| PT24 | Tesouraria › Fluxos de caixa (e Gestão › Fluxos de caixa) | tela | Tesouraria | ? | Redshift | projeto novo: Tesouraria no whitelabel (fluxo de caixa: tela e job juntos) | no ar |
| PT25 | Tesouraria › Mercato Pago › Monitor de liquidações diárias (e botões) | tela | Tesouraria | diário | réplica da cessão, Redshift, disco da VM | Artemis V2 (TS-5705): ela absorve do sistema em diante | no ar |
| PT26 | Tesouraria › Mercato Pago › Baixa massiva (Contratos) | tela | Tesouraria | sob demanda | API da cessão, datawall, Redshift | Artemis V2 (TS-5705) | no ar |
| PT27 | Tesouraria › Mercato Pago › Tratamento manual de File4 | tela | Tesouraria | sob demanda | — | chegada dos dados do MP (TS-5775): vai com o parser do File 4 | no ar |
| PT28 | Tesouraria › Mercato Pago › Estornos | tela | Tesouraria | ? | disco da VM | desligar | no ar |
| PT29 | Tesouraria › Omnis (Liquidação e Alteração de lotes) | tela | Tesouraria | ? | réplica da cessão, API da cessão, datawall, S3, SMTP | Artemis V2 (TS-5705): carga de liquidação Omnis | no ar |
| PT30 | Tesouraria › Padtek › Emissão de boletos | tela | Tesouraria | mensal | Redshift, SMTP, GalaPay | projeto novo: Tesouraria no whitelabel (Padtek, emissão) | no ar |
| PT31 | Tesouraria › Padtek › Cadastro de Devedores, Cadastro de Operações, Consulta de Fluxos e… | tela | Tesouraria | mensal [H] | Redshift, BCB | projeto novo: Tesouraria no whitelabel (Padtek) | no ar |
| PT32 | Tesouraria › Simplix › Gerador de CNAB | tela | Auditoria de Liquidação | diário [H] | Redshift, disco da VM | projeto novo: Tesouraria no whitelabel (Simplix) | no ar |
| PT33 | Tesouraria › Voltis (Cancelamentos e Controle de Liquidações) | tela | Tesouraria | ? | réplica da cessão, Redshift | Artemis V2 (TS-5705): carga de liquidação | no ar |
| PT34 | Portal de incidentes (8506) › Incidentes operacionais | tela | ? | ? | Redshift | portal whitelabel: um módulo de incidentes só, unificando as duas tabelas | no ar |
| PT35 | Fronts desligados: Produtos (8501) e Fórum de Produtos (8511) | tela | ? | ? | — | nada a migrar | desligado |
| PT36 | Rotas legadas /tesouraria/, /compliance/, /formalizacao/, /gestao/ | tela | ninguém | ? | — | desligar (remover as confs do nginx) | 502 (fora do ar) |
| PT37 | (sem menu) /cvm/ativo/{cnpj} e rotas nginx /cvm e /controladoria | tela | ? | ? | CVM | desligar se ninguém de fora consumir (confirmar) | no ar |

### Apagados do repositório (não migram, T18)

| Item | Caminho |
|---|---|
| E-mail 'Valores aprovados' do dia anterior | `Mercato_Libero/Emails/Mail_Valores_Dia_Anterior.py (apagado em 9c2d10b)` |
| Carga VP/PDD por fundo (tela Acompanhamento de Fundos) | `Controladoria/Aplicacoes/App_Carga_VP_PDD_Fundos.py` |
| Alarme de monitor do ETL (Controladoria) | `Controladoria/Alarmes/Alarme_Monitor_ETL.py` |
| Gerador de recálculos de PDD (Controladoria) | `Controladoria/Aplicacoes/App_Gerar_Recalculos_PDD.py` |
| Reconciliador de VP contra o Bluedeck (Controladoria) | `Controladoria/Aplicacoes/App_Reconciliador_VP.py` |
| Reconciliar VP, versão antiga (Controladoria) | `Controladoria/Aplicacoes/Reconciliar_vp.py` |
| Cadastro CVM em capitalis_science.cvm_cad_fi | `Outros/PLGN_Download_Cadastro_Fundos.py` |
| Monitor de notícias CVM/G1 (Jurídico) | `Jurídico/Crawler_CVM.py` |
| Gerador de anexo de CCCB (Jurídico) | `Jurídico/Gerar_Anexo_CCCB.py` |
| Tesouraria: cálculo NDZ | `Tesouraria/Aplicações/App_Calculo_NDZ.py` |
| Tesouraria: fluxo de caixa Dayvale | `Tesouraria/Aplicações/App_Fluxos_de_Caixa_Dayvale.py` |
| Tesouraria: monitor de boletos pagos (FIDC Vektor, GalaPay) | `Tesouraria/Aplicações/App_Monitor_Boletos_Pagos.py` |
| Tesouraria: monitor de suplementos (CVM) | `Tesouraria/Aplicações/App_Monitor_Suplementos.py` |
| OCR: réplica de lastros MeLib para a formalização | `OCR/Aplicações/(Inc) App_Replicate_MeLi_Formalizacao.py` |
| OCR: baixar CCB de um contrato | `OCR/Aplicações/App_Baixar_CCB.py` |
| OCR: termos do MP NP para o bucket do OCR | `OCR/Aplicações/App_Termos_MP_NP.py` |
| OCR: termos do FIDC Fornecedores para o bucket do OCR | `OCR/Aplicações/App_Termos_<cliente>.py` |
| Busca de ISIN na B3 (Anbima.py) | `Bluedeck/Aplicacoes/Anbima.py` |
| Cadastro de enquadramento por IA | `Bluedeck/Aplicacoes/App_Cadastrar_Enquadramento_BD.py` |
| Cadastro de ISIN por IA | `Bluedeck/Aplicacoes/App_Cadastrar_ISIN_BD.py` |
| Cadastro de taxas por IA | `Bluedeck/Aplicacoes/App_Cadastrar_Taxas_Simples_BD.py` |
| Dados cadastrais da CVM para planilha de gestão | `Bluedeck/Aplicacoes/App_Endpoint_Sheet_Gestao.py` |
| Atualização de enquadramento por IA | `Bluedeck/Aplicacoes/App_Update_Enquadramento_BD.py` |
| Exploração da API de eventos (script avulso) | `Bluedeck/Aplicacoes/pull_<gestora>.py` |
| Funções dos monitores legados de covenants | `Compliance/Ferramenta_Covenants/Functions/funcoes_covenants.py` |
| Monitores legados de covenants, front antigo de Compliance e… | `Compliance/App_Monitor_{BGT,Dayvale,Genius}.py;…` |

### Contagem por destino proposto

| Destino | Itens |
|---|---|
| não migra (apagado ou carga já feita) | 29 |
| envio de relatórios (épico TS-5704) | 26 |
| desligar | 23 |
| projeto novo por área (sem cartão) | 19 |
| épico TS-5705 (liquidação MP) | 16 |
| portal whitelabel | 8 |
| chegada dos dados do MP (TS-5775) | 7 |
| apl-shared-service: job agendado | 7 |
| passagem da VM (ações antes de desligar) | 6 |
| a decidir | 6 |
| envio de relatórios, onda nova (sem cartão) | 4 |
| ação antes da saída do Rafael | 1 |
| Service Report MP (TS-5625) | 1 |
| **total** | **153** |

## Perguntas abertas

Por quem responde. A agenda, as listas de e-mail e os usuários do portal se respondem com três
consultas só leitura no Redshift (ver "Fontes").

**Pietro Nett**
- D2: aceitar os destinos propostos, e quem fica com os dois projetos novos (Tesouraria e
  Compliance), com os 4 envios fora dos 25 da TS-5717 e com as ferramentas manuais do Bluedeck.
- D3: data de saída do Rafael, e até quando a máquina e os acessos dele valem.
- A Artemis V2 absorve também as cargas de liquidação fora do Mercato Pago (Omnis e Voltis, PT29 e
  PT33) e a baixa contábil por parcela (MP28)?

**Rafael Frankl, na passagem (TS-5565)**
- O usuário da API do Bluedeck é a conta pessoal dele? As credenciais que ficaram no histórico do
  git já foram trocadas?
- A cópia da VM é igual ao `9c2d10b`? Sobrou alguma linha ativa na agenda apontando para script
  apagado? O orquestrador avisa "script inexistente" só para a caixa dele.
- Quem coloca os arquivos da VLTS I no SFTP, quem grava a pasta de estornos do Mercato Pago e a
  tabela de amortizações programadas do Middle, e quem carrega a posição de passivo do Bluedeck?
- Por que os disparos das 16h e das 18h do fechamento foram desligados? O das 20h45 ainda é
  necessário?

**Tesouraria e operações**
- Retiradas (BGT e Fynvest), estornos e write-off mensal: os administradores e o cliente aceitam
  mudança de remetente e de formato?
- O arquivo extra de PPV ainda chega? O cliente ainda busca o estoque mensal no S3?
- FIDC Fornecedores: a conciliação ainda fecha lote a partir do e-mail "Valores a pagar"? O backfill de 9
  meses das cessões mensais vai ser feito?
- Omnis: quem fecha as parcelas zeradas à mão? A área quer baixa automática como a do Mercato Pago?
- Simplix: quem compara o CNAB gerado com um oficial de um dia inteiro? Quem é dono do ETL das
  tabelas do Simplix no Lake?

**Compliance e Riscos**
- A conferência diária dos covenants globais continua (7 áreas)? O menu está escondido desde 04/11.
- Agendar a apuração automática dos globais (BD17) e corrigir os rótulos trocados dos dois
  processadores na agenda?

**Middle e Controladoria**
- Alguma das 5 telas do Middle escondidas desde 04/11 ainda é usada? E as ferramentas manuais do
  Bluedeck: quem vai rodá-las?
- A Controladoria quer de volta a carga da tela Acompanhamento de Fundos, ou a tela sai?

**Cadastro e Formalização**
- O Cadastro ainda usa as pastas do SharePoint gravadas pelos lastros e pelos termos do FIDC Fornecedores?
  O zip dos termos chega com os PDFs [H: o código parece zipar só as pastas]?
- O acervo da Dots pode ser exportado e a tela desligada?

**Infraestrutura**
- O acesso ao bucket de terceiro do Simplix e o IP novo nos SFTPs (Mercato Pago, empresa e
  parceiro do Voltis Supply) precisam de liberação de quem?

## Fontes

- Repositório de automações, HEAD `9c2d10b` (09/11/2026). Também o README da raiz e os das pastas
  (05/11), o README do Mercato Pago (09/11) e os `MODULO_*.md` do portal. Só leitura.
- Levantamento da Artemis V2 sobre o Mercato Pago (04/11):
  `projects/artemis-v2/tasks/13-automations-survey.md`. As divergências com o HEAD estão acima.
- Datadog, 22/10 a 04/11/2026: chamadas da máquina à cessão, já resumidas em
  `projects/artemis-v2/evidence/mercato-libero-ec2-calls-2026-11-04.md`. Mostra só o que passa
  pela API da cessão; o que vai direto ao banco ou a outros sistemas não aparece ali.
- **Não lido:** a agenda real do orquestrador. O túnel do Redshift estava fechado em 16/11.
  Frequência e ids vêm dos READMEs e do código. Para conferir, três consultas só leitura:
  - a agenda: `mv_schedule_reports`, todas as linhas, com o campo `ativo`;
  - as listas de e-mail: `mv_mail_list` por id, contando internos e externos sem listar os
    endereços;
  - os usuários ativos do portal e as roles de cada um: `mv_usuarios_projetos`.
- Detalhe por item (o que faz, o que grava, evidência `arquivo:linha`, riscos), com os nomes
  reais: `~/.local/share/workspace/projects/vm-migration/inventory/` (um JSON por família,
  `overrides.json` com os destinos ajustados). A tabela acima é gerada desses arquivos.

## Histórico

- 04/11/2026: tarefa criada.
- 16/11/2026: inventário preenchido a partir do repositório e dos READMEs, com destino proposto
  por item; a agenda real ficou para conferir quando o túnel do Redshift estiver aberto.
- 16/11/2026, à tarde: nada fica na VM (T19). Os 25 scripts de envio de relatórios passaram para os
  cards que já existiam, sem card novo (T20); títulos e descrições de 22 cards atualizados no Jira.
