(() => {
  const corpus = document.body.dataset.page;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function renderBars(items, labelKey, maximum, valueKey = 'frequencia') {
    if (!items.length) return '<p class="analysis-status">Sem dados para exibir.</p>';
    return items.map(item => {
      const label = item[labelKey];
      const value = item[valueKey];
      return `<div class="analysis-bar"><span class="analysis-bar-label" title="${escape(label)}">${escape(label)}</span><span class="analysis-bar-track"><span class="analysis-bar-fill" style="display:block;width:${Math.max(3, value / maximum * 100)}%"></span></span><span class="analysis-bar-value">${Number(value).toLocaleString('pt-BR')}</span></div>`;
    }).join('');
  }

  function render(data) {
    const metrics = data.metricas;
    const cards = [
      ['Falas', metrics.falas],
      ['Tokens reconhecidos', metrics.tokens_reconhecidos],
      ['Lemas distintos', metrics.lemas_distintos],
      ['Formas não reconhecidas', metrics.formas_nao_reconhecidas],
    ];
    document.querySelector('#analysisMetrics').innerHTML = cards.map(([label, value]) => `<article class="analysis-metric"><span>${label}</span><strong>${Number(value).toLocaleString('pt-BR')}</strong></article>`).join('');
    const words = data.palavras || [];
    const maxWord = Math.max(...words.map(item => item.frequencia), 1);
    document.querySelector('#wordCloud').innerHTML = words.map(item => `<a href="#transcriptList" data-query="${escape(item.palavra)}" title="${item.frequencia} ocorrências · lema" style="font-size:${Math.round(12 + 23 * item.frequencia / maxWord)}px">${escape(item.palavra)}</a>`).join('');
    document.querySelectorAll('#wordCloud a').forEach(link => link.addEventListener('click', event => {
      event.preventDefault();
      const input = document.querySelector('#searchTranscript');
      input.value = link.dataset.query;
      input.dispatchEvent(new Event('input', {bubbles: true}));
      document.querySelector('#transcriptList').scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }));
    document.querySelector('#topTerms').innerHTML = renderBars(words.slice(0, 15), 'palavra', maxWord);
    const phrases = data.combinacoes || [];
    document.querySelector('#topPhrases').innerHTML = renderBars(phrases, 'frase', Math.max(...phrases.map(item => item.frequencia), 1));
    const themes = data.temas || [];
    document.querySelector('#topicStats').innerHTML = renderBars(themes, 'tema', Math.max(...themes.map(item => item.falas), 1), 'falas');
    document.querySelector('#speakerStats').innerHTML = (data.participantes || []).map(person => `<tr><td>${escape(person.nome)}</td><td>${Number(person.falas).toLocaleString('pt-BR')}</td><td>${Number(person.palavras).toLocaleString('pt-BR')}</td><td>${Number(person.percentual_palavras).toLocaleString('pt-BR')}%</td></tr>`).join('');
    document.querySelector('#analysisStatus').textContent = data.metodo || '';
  }

  const bundled = window.CINEPET_TRANSCRIPT_ANALYSES;
  if (bundled?.[corpus]) {
    render(bundled[corpus]);
  } else {
    fetch('dados/analises_textuais.json')
      .then(response => {
        if (!response.ok) throw new Error('Não foi possível carregar a análise textual.');
        return response.json();
      })
      .then(analyses => render(analyses[corpus]))
      .catch(error => { document.querySelector('#analysisStatus').textContent = error.message; });
  }
})();
