# Motor 0.2.0: medições, investigação e referência

## O que mudou

A pontuação antiga 50/100 de sample peak/correlação foi retirada. O relatório
exibe medições, trechos de atenção e testes de escuta. As cinco notas aparecem
na comparação com uma versão de referência escolhida pelo usuário, inclusive
uma música diferente da biblioteca. Não existe nota geral de qualidade.

A referência usa o fluxo normal de upload e seus limites: cinco WAVs/música,
40 WAVs/biblioteca. Não envia áudio a terceiros e não altera nenhum WAV.
Use referências com a mesma taxa de amostragem e compare arranjos equivalentes.
Não há alinhamento temporal automático nem normalização do áudio reproduzido.
O ajuste de ganho sugerido é a diferença de LUFS para escuta na DAW, não um
processamento aplicado pelo sistema; valores positivos podem causar clipping.

## Loudness

FFmpeg empacotado por `imageio-ffmpeg==0.6.0`, executado sem shell, uma thread,
com timeout de 90 s. São lidos somente `input_i`, `input_tp`, `input_lra` do
primeiro passe `loudnorm`; a saída vai para null. Não há correção/renderização
salva. O relatório registra a versão do FFmpeg usada em cada plataforma.

- LUFS integrado: loudness com ponderação e gates BS.1770 implementados no FFmpeg.
- True peak: estimativa por sobreamostragem do filtro loudnorm, em dBTP.
- LRA: variação estatística de loudness, em LU; omitida abaixo de 30 s como
  precaução de interpretação, não como uma duração mínima exigida pela norma.
- Pico/loudness: true peak menos LUFS integrado; não confundir com crest peak/RMS.
- Silêncio: sem pontuação nem loudness fictício; valores não finitos viram null.

Não declaramos certificação de conformidade EBU. Testes verificam seno 1 kHz,
mono/estéreo, true peak acima do sample peak e o caso sintético de dois níveis
separados por 10 dB do EBU Tech 3342. O teste LRA exige 10 ±1 LU.

## Descritores por segundo

STFT Hann de até 2048 amostras, overlap 50%, dentro de blocos de um segundo.
Não há janelas cruzando as fronteiras desses blocos. Potências de L/R são
calculadas antes da média, preservando energia em contrafase. Não são stems.

Bandas: 20–60, 60–250, 250–500, 500–2000, 2000–6000 e 6000–20000 Hz
(limitadas por Nyquist). O relatório global mantém Welch 4096, portanto pode
haver pequenas diferenças entre a média global e a tabela por segundo.

Clareza é representada por **descritores**, não por inteligibilidade vocal:

- centroide ponderado por potência entre 20 Hz e min(20 kHz, Nyquist);
- planicidade: média geométrica/aritmética com piso numérico de 1e-20;
- contraste por banda: 10log10(P90/P10) dos bins, média das bandas válidas;
- agregação: mediana dos segundos com RMS acima de −120 dBFS.

Estéreo por faixa: parte real do cross-power / sqrt(energia L × energia R),
e energia Side. A correlação espectral local não é idêntica à Pearson global
com DC removido. Alertas locais exigem correlação <−0.15 e energia da faixa >1%.
Largura baixa não é tratada como defeito e não dispara incentivo automático a
usar expansores.

## Ataques

Envelope RMS em frames de 10 ms, pico local com proeminência >=4 dB, distância
mínima de 80 ms e nível acima de −60 dBFS. Subida = vale nos 200 ms anteriores
até pico. O detector não distingue bateria, consoante ou outro instrumento.
Quantidade é informativa. A resolução e os limiares limitam a sensibilidade.

Crest em 40–250 Hz usa filtro Butterworth causal de ordem 4, com estado contínuo
entre blocos. O filtro pode alterar a forma do ataque; não é uma medida direta
da qualidade do kick. Eventos exibidos são limitados aos primeiros 200 e o
relatório informa truncamento. Nenhum descritor prova "preservação" sem original.

## Fórmula das cinco notas

Para cada indicador disponível: `d = min(1, abs(atual − referência)/escala)`.
Nota = `round(100 × (1 − média(d)))`. Pesos iguais entre componentes disponíveis.
A interface mostra diferenças, escalas e cobertura; zero componentes = sem nota.
Escalas são heurísticas explícitas de distância, não limites científicos de
qualidade. Não foram calibradas contra julgamentos de engenheiros.

| Dimensão | Indicadores / escala de distância máxima |
|---|---|
| Frequências | 6 proporções de banda / 6 dB cada; delta = 10log10(atual/ref), piso 0.01%; bandas com ambas <0.01% omitidas |
| Dinâmica | LUFS / 6 LU; LRA / 6 LU; crest global / 6 dB |
| Estéreo | correlação / 0.5; energia Side / 25 pontos percentuais; downmix mono / 6 dB |
| Clareza | contraste / 12 dB; planicidade / 0.2; centroide / 3000 Hz |
| Transientes | subida / 100 ms; contraste local / 12 dB; crest grave / 8 dB |

Um sinal idêntico pode receber 100 mesmo sendo ruim. Uma boa mix de arranjo
muito diferente pode receber nota baixa. A versão do motor precisa coincidir;
relatórios antigos precisam de reanálise. As diferenças espectrais não são
valores de EQ a aplicar diretamente.

## Investigação e histórico

Cada dica liga evidência a teste de escuta, trecho e pergunta. Os plugins são
contexto declarado; nomes são apresentados apenas quando a função informada
é pertinente ao teste. Sem thresholds inventados, identificação de vocal por
espectro global ou causalidade automática. Respostas continuam sendo relatos.

Reanálise reutiliza WAV/sessão, arquiva relatório e respostas anteriores e ocupa
um slot da mesma fila limitada. Até dez relatórios anteriores por versão.
A tabela `analysis_history` é criada idempotentemente; versão antiga do app
ignora a tabela adicional. Não remover banco nem WAVs na atualização.

O subprocesso DSP e seus filhos FFmpeg são encerrados juntos no timeout de 180 s.
Os limites systemd existentes continuam válidos. Sem GPU, LLM ou serviço pago.

## Fontes técnicas

- https://ffmpeg.org/ffmpeg-filters.html#loudnorm
- https://tech.ebu.ch/docs/tech/tech3342.pdf
- https://github.com/imageio/imageio-ffmpeg
