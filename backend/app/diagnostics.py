"""Deterministic listening checks tied to measured evidence and declared chains."""


def enrich(report, session):
    m=report['metrics']; timeline=m['timeline']; findings=[]
    def add(key,title,evidence,action,question,category,start=None,confidence='low'):
        findings.append({'id':key,'hypothesis':title,'evidence':evidence,'recommendation':action,
                         'question':question,'category':category,'start_s':start,'confidence':confidence})
    active=[t for t in timeline if t['active']]
    def worst(metric):
        values=[t for t in active if t.get(metric) is not None]
        return max(values,key=lambda t:t[metric]) if values else None
    if m['silent']:
        add('silence','Sinal quase nulo: confirme o bounce.','RMS global abaixo de −160 dBFS.',
            'Confira se os canais e o master estavam ativos ao exportar.','A exportação reproduz áudio na DAW?','dynamics')
    else:
        if m.get('true_peak_dbtp') is not None and m['true_peak_dbtp']>-.5:
            add('truepeak','Pouca margem para picos reconstruídos.',f"True peak {m['true_peak_dbtp']:.2f} dBTP; sample peak {m['sample_peak_dbfs']:.2f} dBFS.",
                'Compare o limiter com true-peak ligado e ceiling mais baixo, igualando o volume. Escolha a margem conforme a entrega; não normalize automaticamente para −14 LUFS.',
                'Qual limiter está no master, qual o ceiling e a redução máxima?','dynamics',confidence='medium')
        if m.get('lra_lu') is not None:
            add('loudness','Confira o movimento entre as seções.',f"LUFS integrado {m['integrated_lufs']:.2f}; LRA {m['lra_lu']:.2f} LU; crest {m['crest_db']:.2f} dB.",
                'Compare verso e refrão com uma referência de intenção semelhante. LRA descreve variação entre trechos; não identifica compressão excessiva sozinha.',
                'Você queria um master constante ou mais contraste entre verso e refrão?','dynamics')
        bass=[t for t in active if t['bands']['sub']['energy_pct'] is not None]
        if bass:
            t=max(bass,key=lambda t:t['bands']['sub']['energy_pct']+t['bands']['bass']['energy_pct'])
            share=t['bands']['sub']['energy_pct']+t['bands']['bass']['energy_pct']
            add('lowbalance','Revise o equilíbrio dos graves neste trecho.',f"{t['start_s']}–{t['end_s']:.1f} s: {share:.1f}% da potência espectral entre 20–250 Hz.",
                'Ouça esse trecho com a referência em volume semelhante. Se o grave encobrir outros elementos, teste reduzir o 808 ou o beat antes de cortar o master. A porcentagem, isoladamente, não prova excesso.',
                'Nesse trecho o grave sustenta a intenção ou dificulta ouvir a letra/kick?','frequencies',t['start_s'])
        bright=worst('centroid_hz')
        if bright:
            add('brightness','Confira brilho e aspereza no trecho mais brilhante.',f"{bright['start_s']}–{bright['end_s']:.1f} s: centroide {bright['centroid_hz']:.0f} Hz.",
                'Compare pratos, hats e consoantes por escuta. Só teste de-esser no vocal se as consoantes forem o problema; energia aguda no mix também pode vir da bateria.',
                'O incômodo vem de consoantes, hats, distorção ou não há incômodo?','clarity',bright['start_s'])
        for band in ('sub','bass','mid','presence','air'):
            rows=[t for t in active if t['bands'][band]['correlation'] is not None]
            if rows:
                t=min(rows,key=lambda t:t['bands'][band]['correlation']);corr=t['bands'][band]['correlation']
                if corr<-.15 and (t['bands'][band]['energy_pct'] or 0)>1:
                    add('phase-'+band,'Possível cancelamento localizado ao ouvir em mono.',f"{t['start_s']} s; faixa {band}; correlação {corr:.2f}; energia {t['bands'][band]['energy_pct']:.1f}%.",
                        'Ouça em mono e faça bypass dos expansores/delays de estéreo, um por vez. Não aumente a largura para perseguir uma nota.',
                        'Qual elemento perde corpo nesse trecho em mono?','stereo',t['start_s'],confidence='medium')
        if not any(h['category']=='stereo' for h in findings):
            add('stereocheck','Confira largura sem perder o centro.',f"Energia Side: {m.get('side_energy_pct')}; correlação global: {m.get('lr_correlation')}.",
                'Compare estéreo e mono. Mix estreito pode ser intencional; avalie adlibs, ambiências e backing vocals separadamente na DAW.',
                'Você quer mais espaço nos apoios ou preservar uma imagem central?','stereo')
        if m['transient_event_count']>=3:
            event=max(m['transient_events'],key=lambda e:e['contrast_db'])
            add('attacks','Confira o contraste dos ataques.',f"{m['transient_event_count']} eventos; subida mediana {m['attack_median_ms']:.1f} ms; contraste local mediano {m['attack_contrast_median_db']:.1f} dB; crest 40–250 Hz {m['low_band_crest_median_db']} dB.",
                'Compare compressor/limiter com bypass e ganho igualado. Se o ataque perder impacto, teste menor redução e ataque mais lento. O mix final não revela quanto foi perdido em relação ao original.',
                'Os ataques ficam mais claros quando você reduz o trabalho do limiter?','transients',event['time_s'])
        else:
            add('fewattacks','Poucos ataques distinguíveis pelo detector.',f"{m['transient_event_count']} eventos com proeminência mínima de 4 dB e distância de 80 ms.",
                'Confira se o trecho é sustentado ou se os ataques estão pouco destacados. Não conclua sobrecompressão apenas por este indicador.',
                'Há bateria marcada no trecho ou o arranjo é sustentado?','transients')
    # Keep declared-chain questions; add plugin-aware experiments without fabricated settings.
    for h in report['hypotheses']:
        if h['id'].startswith(('chain-','order-')):
            h['recommendation']='Faça bypass de um estágio por vez com ganho de saída compensado; anote redução de ganho e mudança audível. A ordem não é uma regra universal.'
            findings.append(h)
    for h in findings:
        kinds={'dynamics':('compressor','limiter'),'frequencies':('eq',),'clarity':('eq','reverb','saturation'),'stereo':('delay','reverb'),'transients':('compressor','limiter')}.get(h.get('category'),())
        plugins=[f"{c['name']}: {p['name']}" for c in session['channels'] for p in c['plugins'] if not p['bypass'] and p['kind'] in kinds]
        h['declared_plugins']=plugins[:8]
    report['hypotheses']=findings
    # Objective gates derived from the installed measurement/mixing guidance.
    # These are checks, not a universal quality grade or a perceptual verdict.
    peak = m.get('sample_peak_dbfs')
    true_peak = m.get('true_peak_dbtp')
    mono = m.get('mono_downmix_change_db')
    checks = []
    def check(key, label, status, evidence, next_step):
        checks.append({'id': key, 'label': label, 'status': status,
                       'evidence': evidence, 'next_step': next_step})
    check('source_decode', 'Formato e decodificação', 'pass',
          f"{m['channels']} canal(is), {m['sample_rate_hz']} Hz, {m['subtype']}, {m['duration_s']:.2f} s.",
          'Nenhuma ação técnica indicada pelo formato.')
    if peak is None:
        check('sample_peak', 'Pico de amostra', 'indeterminate', 'Pico não disponível.', 'Reanalise o WAV.')
    elif peak >= -0.01:
        check('sample_peak', 'Pico de amostra', 'warning', f'{peak:.2f} dBFS; há amostras próximas de full scale.', 'Confira clipping e o ceiling no master.')
    else:
        check('sample_peak', 'Pico de amostra', 'pass', f'{peak:.2f} dBFS.', 'Nenhuma amostra próxima de full scale foi encontrada.')
    if true_peak is None:
        check('true_peak', 'True peak', 'indeterminate', 'True peak não disponível.', 'Reanalise com o medidor de loudness habilitado.')
    elif true_peak > -1:
        check('true_peak', 'True peak', 'warning', f'{true_peak:.2f} dBTP; a margem depende da entrega.', 'Confira a especificação do destino e o limiter true-peak.')
    else:
        check('true_peak', 'True peak', 'pass', f'{true_peak:.2f} dBTP.', 'Ainda valide o arquivo exportado após qualquer codec.')
    if mono is None:
        check('mono', 'Compatibilidade mono', 'not_evaluated', 'Mono não foi calculado para este arquivo.', 'Use um WAV estéreo para avaliar o downmix.')
    elif mono < -1:
        check('mono', 'Compatibilidade mono', 'warning', f'Downmix medido em {mono:.2f} dB.', 'Ouça em mono e investigue a faixa/efeito que perde corpo.')
    else:
        check('mono', 'Compatibilidade mono', 'pass', f'Downmix medido em {mono:.2f} dB.', 'Confirme por escuta em mono; o número não isola instrumentos.')
    check('loudness_target', 'Meta de loudness', 'not_evaluated',
          'Nenhum destino (streaming, broadcast ou vídeo) foi especificado.',
          'Escolha o destino antes de tratar LUFS como aprovação ou reprovação.')
    report['checks'] = checks
    report['scores']=[{'category':c,'score':None,'provisional':True,'reason':'Selecione uma versão de referência na comparação para calcular proximidade com fórmula explícita. Os indicadores e testes de escuta abaixo já estão disponíveis.'} for c in ('frequencies','dynamics','stereo','clarity','transients')]
    report['warnings']=[w for w in report['warnings'] if 'não implementados' not in w and 'Pontuações' not in w]
    report['warnings'] += ['As notas de referência medem semelhança de descritores, não qualidade musical; não há nota geral.',
        'Contraste/planicidade/centroide não medem inteligibilidade vocal ou separação de instrumentos.',
        'Ataques são eventos no envelope do mix; a resolução é 10 ms. Preservação de transientes exige comparar uma versão anterior.',
        'LRA não é exibida abaixo de 30 segundos. Trechos com formatos ou arranjos diferentes podem não ser comparáveis.']
    report['methods'].update({'loudness':m['loudness_engine']+'; only input_i/input_tp/input_lra; no output audio saved.',
        'clarity':'STFT Hann 2048, 50% overlap within 1s windows; average channel powers; median centroid/flatness and per-band 90th/10th-percentile contrast; excludes RMS < -120 dBFS.',
        'band_stereo':'Real spectral cross-power / sqrt(L power × R power), by band and 1s block; differs from DC-removed global Pearson.',
        'transients':'10ms RMS envelope, local-peak prominence >=4dB, spacing >=80ms; valley within previous 200ms to peak; 40–250Hz Butterworth order 4 causal bandpass crest.',
        'scoring':'No quality score. Reference comparison: 100*(1-mean(min(1,abs(delta)/scale))); same-engine only; missing metrics excluded with coverage shown.',
        'guidance':'Checks separate pass/warning/indeterminate/not_evaluated; thresholds are delivery checks, not mainstream quality targets.'})
    return report
