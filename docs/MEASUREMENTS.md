# Atualização 0.2.0

Consulte [ANALYSIS_V2.md](ANALYSIS_V2.md) para as medições e notas atuais.
O texto abaixo documenta o motor 0.1.0, mantido para interpretar relatórios antigos.

# Medições — motor 0.1.0

O original não é modificado. Relatórios guardam SHA-256, motor, formato detectado
e contexto declarado. Ausência de evidência é `null`, nunca Infinity ou nota inventada.

| Medição | Método | Limite |
|---|---|---|
| Sample peak | Máximo absoluto; 20 log10 | Não detecta picos intersample |
| RMS | Raiz da média quadrática de todos os canais/amostras | Sem ponderação/gating; não é LUFS |
| Crest | 20 log10(pico/RMS), global e mediana por segundo | Depende do arranjo; não mede compressão de vocal isolado |
| Near full scale | Percentual de amostras ≥ 1−1/32768 | Limiar fixo ~−0,00027 dBFS; não prova clipping audível |
| DC | Média por canal | Descritivo |
| Espectro | Welch/Hann até 4096 amostras, overlap 50%, sem detrend | Média de potência dos canais, sem cancelamento por downmix |
| Faixas | Soma PSD × resolução Hz / potência de todos os bins | Potência, não loudness ou instrumento |
| Correlação | Pearson L/R com DC removido, arquivo completo | Pode ocultar problemas locais; indefinido para canais constantes |
| Mono | Energia de (L+R)/2 / média de potência L/R; 10 log10 | Piso −120 dB para cancelamento total |
| Side | Energia de (L−R)/2 / (mid+side) | Não equivale ao controle de largura da DAW |

Leitura em blocos de 1 segundo limita RAM. Espectro ponderado pela duração do bloco;
janelas reiniciam a cada bloco. Cauda de uma amostra participa de RMS/pico, não do
espectro. A 48 kHz, resolução ~11,72 Hz; subgrave tem poucos bins. Faixas: 20–60,
60–250, 250–500, 500–2000, 2000–6000 e 6000–20000 Hz (bin 20 kHz incluído).
A soma pode ser <100%: DC, <20 Hz e >20 kHz permanecem no denominador.

## Pontuações provisórias

Não existe curva TRAP universal ou média geral. As notas são convenções de triagem,
não probabilidades, avaliação estética ou calibração perceptiva.

- Frequências: nulo. Distribuição é descritiva.
- Dinâmica: 50 se sample peak próximo/acima de full scale; 100 caso contrário.
  Só verifica esse indicador; não avalia loudness ou compressão.
- Estéreo: 50 se correlação <0; 100 caso contrário. Nulo para mono, silêncio ou
  correlação indefinida. 100 não garante compatibilidade mono em cada trecho.
- Clareza: nulo. Mascaramento e presença precisam de escuta.
- Transientes: nulo. Crest é proxy global, sem detecção de ataques individuais.
- Silêncio/quase silêncio (RMS <1e-8): nenhuma nota positiva.

## Investigação e comparação

Gatilhos: full scale, correlação negativa, crest <6 dB, dois ou mais estágios de
dinâmica no mesmo canal, compressor seguido de EQ. Ordem de plugins nunca é uma
regra: ambas as posições de EQ podem ser válidas. Toda hipótese tem evidência,
confiança baixa e pergunta. Nada medido no mix é atribuído a um canal isolado.

Respostas são relatos do usuário, atualizáveis por versão, com timestamp. Ficam
junto da pergunta original; “não sei” preserva a incerteza. Não há interpretação
automática de texto para diagnóstico final.

A/B mostra A, B e B−A, diferença de duração e aviso de motores distintos. Não
alinha, normaliza ou declara vencedor. Escuta comparativa exige trechos equivalentes
e loudness igualado na DAW. LUFS/BS.1770 e true peak precisam de implementação e
validação com sinais de conformidade antes de habilitar valores.

## Referências

- [SciPy Welch](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)
- [SoundFile](https://python-soundfile.readthedocs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js App Router](https://nextjs.org/docs/app)
