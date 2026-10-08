(() => {
  const type = document.body.dataset.resource;
  const dataPath = document.body.dataset.data || 'recursos/dados.json';
  const $ = selector => document.querySelector(selector);
  const fold = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const colors = ['#155d5d','#b34f25','#28548a','#805900','#65428f','#4e682f','#913745','#1d6e85','#81511d','#3b528e','#36664b'];
  const colorFor = (key, keys) => colors[Math.max(0, keys.indexOf(key)) % colors.length];

  fetch(dataPath).then(response => {
    if (!response.ok) throw new Error('Não foi possível carregar os dados deste recurso.');
    return response.json();
  }).then(data => {
    if (type === 'respostas') renderAnswers(data);
    if (type === 'palavras') renderWords(data);
    if (type === 'proporcoes') renderProportions(data);
    if (type === 'antiga') renderOldTranscript(data);
  }).catch(error => {
    const target = $('#resourceContent');
    if (target) target.innerHTML = `<p class="empty-state">${escape(error.message)}</p>`;
  });

  function renderAnswers(data) {
    const eventSelect = $('#eventFilter');
    const questionSelect = $('#questionFilter');
    const search = $('#answerSearch');
    const count = $('#resourceCount');
    const list = $('#resourceContent');
    const events = [...new Set(data.respostas.map(answer => answer.evento))].sort();
    const questions = [...new Set(data.respostas.map(answer => answer.pergunta))].sort();
    events.forEach(value => eventSelect.add(new Option(value, value)));
    questions.forEach(value => questionSelect.add(new Option(value, value)));
    const queryParam = new URLSearchParams(location.search).get('q') || '';
    search.value = queryParam;
    const filtered = () => data.respostas.filter(answer =>
      (!eventSelect.value || answer.evento === eventSelect.value)
      && (!questionSelect.value || answer.pergunta === questionSelect.value)
      && (!search.value || fold(`${answer.resposta} ${answer.pergunta} ${(answer.temas || []).join(' ')}`).includes(fold(search.value))));
    const render = () => {
      const answers = filtered();
      count.textContent = `${answers.length.toLocaleString('pt-BR')} respostas`;
      list.innerHTML = answers.length ? answers.map(answer => {
        const person = data.participantes[answer.id_resposta] || {};
        return `<article class="answer-card"><div class="answer-meta"><span>${escape(answer.evento)}</span><span>${escape(person.curso)}</span><span>ID ${escape(answer.id_resposta)}</span></div><h2>${escape(answer.pergunta)}</h2><p>${escape(answer.resposta)}</p><div class="chips">${(answer.temas || []).map(theme => `<span class="chip">${escape(theme)}</span>`).join('')}</div></article>`;
      }).join('') : '<p class="empty-state">Nenhuma resposta corresponde aos filtros.</p>';
    };
    [eventSelect, questionSelect].forEach(input => input.addEventListener('change', render));
    search.addEventListener('input', render);
    render();
  }

  function renderWords(data) {
    const max = Math.max(...data.palavras.map(word => word.frequencia), 1);
    $('#resourceCount').textContent = `${data.palavras.length.toLocaleString('pt-BR')} termos recorrentes`;
    $('#resourceContent').innerHTML = `<div class="word-cloud">${data.palavras.map(word => `<a href="respostas.html?q=${encodeURIComponent(word.palavra)}" style="font-size:${Math.round(13 + 22 * word.frequencia / max)}px" title="${word.frequencia} ocorrências">${escape(word.palavra)}</a>`).join('')}</div><nav class="theme-list" aria-label="Filtrar por tema">${data.temas.map(theme => `<a href="respostas.html?q=${encodeURIComponent(theme)}">${escape(theme)}</a>`).join('')}</nav>`;
  }

  function renderProportions(data) {
    const select = $('#eventFilter');
    Object.keys(data.contagem_participantes_evento).sort().forEach(value => select.add(new Option(value, value)));
    const render = () => {
      const event = select.value;
      const denominator = data.contagem_participantes_evento[event] || 0;
      const answers = data.respostas.filter(answer => answer.evento === event);
      const questions = [...new Set(data.respostas.map(answer => answer.pergunta))].sort();
      const values = questions.map(question => {
        const answered = answers.filter(answer => answer.pergunta === question && String(answer.resposta || '').trim() && !['.', '-', '—'].includes(String(answer.resposta).trim())).length;
        return {question, answered, percent: denominator ? Math.round(answered / denominator * 100) : 0};
      });
      $('#resourceCount').textContent = `${denominator.toLocaleString('pt-BR')} participantes no evento`;
      $('#resourceContent').innerHTML = values.map(item => `<article class="proportion-row"><span class="proportion-question">${escape(item.question)}</span><div class="proportion-track" role="img" aria-label="${item.percent}% dos participantes"><div class="proportion-fill" style="width:${item.percent}%"></div></div><span class="proportion-value"><strong>${item.percent}%</strong><small>${item.answered}/${denominator}</small></span></article>`).join('');
    };
    select.addEventListener('change', render);
    render();
  }

  function renderOldTranscript(data) {
    const speakerSelect = $('#speakerFilter');
    const search = $('#transcriptSearch');
    const list = $('#resourceContent');
    const speakers = [...new Set(data.transcricao.map(row => row.participante))];
    speakers.forEach(value => speakerSelect.add(new Option(value, value)));
    search.value = new URLSearchParams(location.search).get('q') || '';
    const render = () => {
      const rows = data.transcricao.filter(row => (!speakerSelect.value || row.participante === speakerSelect.value)
        && (!search.value || fold(`${row.fala} ${row.temas.join(' ')}`).includes(fold(search.value))));
      $('#resourceCount').textContent = `${rows.length.toLocaleString('pt-BR')} falas`;
      list.innerHTML = rows.length ? rows.map(row => {
        const hue = colorFor(row.participante, speakers);
        return `<article class="old-speech"><div class="old-speaker" style="--speaker-color:${hue}">${escape(row.participante)}</div><div class="old-speech-content"><time>Fala ${String(row.ordem).padStart(3,'0')}</time><p>${escape(row.fala)}</p><div class="chips">${row.temas.map(theme => `<span class="chip">${escape(theme)}</span>`).join('')}</div></div></article>`;
      }).join('') : '<p class="empty-state">Nenhuma fala corresponde aos filtros.</p>';
    };
    speakerSelect.addEventListener('change', render);
    search.addEventListener('input', render);
    render();
  }
})();
