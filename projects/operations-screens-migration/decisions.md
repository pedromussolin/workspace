Status: rascunho
Data: 04/11/2026
Tags:

# Decisões

Uma decisão por linha, com dono e data. Quando uma pendente fechar, ela vai para "Tomadas" com o motivo.

## Pendentes

Em "Quem", quem decide.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| D1 | Nome definitivo do projeto (hoje provisório) | Pietro Nett | 04/11/2026 | o nome depende do que o inventário mostrar |
| D2 | Para onde vai cada item: repo existente, app novo, outra ferramenta ou desligar | Pietro Nett | 04/11/2026 | só dá para decidir depois do inventário (tarefa 01) |
| D3 | O que acontece com a EC2 de automações e com os acessos do Rafael Frankl na saída dele | a definir | 04/11/2026 | define o prazo: tudo o que roda ali para quando a máquina ou o acesso pararem |
| D4 | Processamento do Service Report no apl-shared-service: **provisório**, só o `openpyxl` como dependência nova (para os `.xlsx`) e os CSVs lidos uma vez, em partes, somando só os agregados, em vez de pandas + openpyxl copiando o código antigo. Validar com outros desenvolvedores antes do PR | Heitor, com outros desenvolvedores | 11/11/2026 | o shared-service não tem pandas nem openpyxl [C]; ler em partes evita carregar os 2,6 GB do consumer na memória do worker, mas o código é reescrito, e a comparação com a tela antiga na fase em paralelo é o que garante que os números batem |

## Tomadas

Em "Quem", quem decidiu.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| T1 | Separar a saída do Rafael Frankl em dois projetos: liquidação do Mercato Libero na Artemis V2 e telas de operações aqui | Pietro Nett | 04/11/2026 | a liquidação já é o domínio da Artemis V2 (fechamento de lotes); as telas são outro público e outro ciclo |
| T2 | Tela Service Report (Middle, Mercato Pago): a migração para o portal se limita ao que a tela faz hoje na EC2 de automações. Os cinco arquivos (pool mix, ZIP do datatape, faixas DPD, PDD por faixa e vintage) são só para download; nenhuma integração de entrega (cessão, administrador ou cliente) | Heitor | 11/11/2026 | o time de operações confirmou que baixa os arquivos, monta à mão um report maior e o envia ao cliente; os destinos do §1 da spec de handoff estão errados, e nenhum deles aparece no código nem no Datadog [C] |
| T3 | Service Report: os campos "Faixas DPD — De/Até" (DPD = dias de atraso) saem da tela e entra um campo "Data da PDD", preenchido com a data do datatape (a fita da carteira que o cliente manda) e editável. O arquivo de faixas sai sempre, e a tela avisa quando a PDD vier vazia | Heitor | 11/11/2026 | as datas não mudam nenhum arquivo: só liberam o de faixas, e o "Até" vira a data da PDD [C]. O cálculo que as usava (saldo que passou de 30 dias de atraso no período) só existia no script antigo e não volta; se operações pedir, entra como acréscimo |
| T4 | Service Report no portal, em quatro repositórios: data-lake-api (PDD e a tabela da vintage no Redshift), apl-shared-service (navegação no S3, processamento e arquivos gerados), BFF e front. Módulo novo `mp-reports` (pasta `mp_reports`) no data-lake-api e no shared-service; branch `feat/TS-5625-service-report-mp`. Menu: Módulos › Middle › Relatórios MP | Heitor | 11/11/2026 | o data-lake-api já conecta no Redshift e faz DELETE e INSERT numa transação só; o shared-service já tem S3, Celery e agendador [C] |
| T5 | Estado do job em `scheduler.job_executions` (disparo MANUAL de um agendamento desativado) e progresso no Redis, com uma chave por execução, expiração e `updated_at` como sinal de vida | Heitor | 11/11/2026 | não cria tabela; a API e o worker são processos separados, então o estado não pode ficar em memória como na EC2 de automações [C] |
| T6 | Configuração por variável de ambiente no shared-service: CNPJ do fundo, credenciais, bucket e pasta do S3 do datatape, bucket de saída e dias de retenção dos arquivos gerados (limpeza por tarefa agendável, como a do disparo de e-mails) | Heitor | 11/11/2026 | padrão `CFG_{CONTEXTO}_{NOME}` dos repositórios; nada fixo no código |
| T7 | Grupo novo "Middle" no portal para as roles da tela | Heitor | 11/11/2026 | não existe grupo de Middle hoje; os grupos são Operações, Gestão, Risco, Produtos e outros [C] |
| T8 | Aceitas as recomendações de 11/11: o worker monta os `.xlsx`; gravação da vintage desligada por padrão; LOCK na tabela (ou lock no Postgres do data-lake-api, se faltar permissão); backend recusa `.filepart`, `TEST/` e arquivos de outro fundo; uma rodada por vez; aviso após 10 min sem progresso e falha após 45 min; porte fiel (três leituras do CSV); lista de rodadas de todos; rota e escopo `mp-reports` (`read` e `run`); download pelo BFF; página única; consulta de status a cada 3 s; rodar em paralelo com a tela antiga e comparar os arquivos antes de desligá-la | Heitor | 11/11/2026 | sem mudança sobre o que foi proposto |
