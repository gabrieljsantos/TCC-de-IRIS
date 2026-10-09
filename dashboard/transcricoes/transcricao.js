(() => {
  const page = document.body.dataset.page;
  const configs = {
    posicoes: {
      citationTitle: 'O Perigo de uma História Única',
      data: 'dados/perigo-historia-unica.json',
      index: 'dados/indice-perigo-historia-unica.json',
      tracks: {
        posicao2: { src: '../media/posicao-2.mp3', offsetMs: 0, label: 'Posição 2' },
        posicao1: { src: '../media/posicao-1.mp3', offsetMs: 142600, label: 'Posição 1' },
      },
    },
    reflexao: {
      citationTitle: 'Reflexão sobre Wicked',
      data: 'dados/reflexao-wicked.json',
      index: 'dados/indice-reflexao-wicked.json',
      tracks: {
        reflexao: { src: '../media/reflexao-wicked.mp3', offsetMs: 0, label: 'Reflexão' },
      },
    },
  };
  const config = configs[page];
  if (!config) return;

  const player = document.querySelector('#audioPlayer');
  const sourceSelect = document.querySelector('#audioSource');
  const list = document.querySelector('#transcriptList');
  const participantFilter = document.querySelector('#participantFilter');
  const searchInput = document.querySelector('#searchTranscript');
  const currentTime = document.querySelector('#currentTime');
  const playerMessage = document.querySelector('#playerMessage');
  const resultCount = document.querySelector('#resultCount');
  const participantLegend = document.querySelector('#participantLegend');
  const transcriptScroll = document.querySelector('.transcript-scroll');
  const selectionCount = document.querySelector('#selectionCount');
  const clearSelection = document.querySelector('#clearSelection');
  const copySelection = document.querySelector('#copySelection');
  const toggleGrouping = document.querySelector('#toggleGrouping');
  let rows = [];
  let displayRows = [];
  let groupingEnabled = true;
  const selectedIds = new Set();
  let participantNames = new Map();
  let participantColors = new Map();
  let activeId = null;
  let stopAtTrackMs = null;
  let currentTrackKey = sourceSelect.value;
  searchInput.value = new URLSearchParams(location.search).get('q') || '';

  const pad = (n, width = 2) => String(n).padStart(width, '0');
  const formatMs = value => {
    const ms = Math.max(0, Math.floor(value || 0));
    const hours = Math.floor(ms / 3600000);
    const minutes = Math.floor(ms % 3600000 / 60000);
    const seconds = Math.floor(ms % 60000 / 1000);
    const millis = ms % 1000;
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}.${pad(millis, 3)}`;
  };
  const formatCompactMs = value => {
    const ms = Math.max(0, Math.floor(value || 0));
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor(ms % 60000 / 1000);
    const millis = ms % 1000;
    return `${pad(minutes)}:${pad(seconds)}.${pad(millis, 3)}`;
  };
  const activeTrack = () => config.tracks[sourceSelect.value];
  const eventTimeMs = () => Math.round(player.currentTime * 1000)
    + (config.tracks[currentTrackKey] || activeTrack()).offsetMs;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const normalizeText = value => String(value ?? '').toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const palette = ['#155d5d','#b34f25','#28548a','#805900','#65428f','#4e682f','#913745','#1d6e85','#81511d','#3b528e','#36664b'];

  function normalizeSegment(segment) {
    return {
      ...segment,
      pid: segment.participante_id || segment.participante_indice || 'P00',
      startMs: Number(segment.inicio_ms ?? Math.round(Number(segment.inicio || 0) * 1000)),
      endMs: Number(segment.fim_ms ?? Math.round(Number(segment.fim || 0) * 1000)),
      confidence: Number(segment.identificacao_confianca_percentual ?? 0),
    };
  }

  function renderLegend(index) {
    const participants = index.participantes || [];
    participantNames = new Map(participants.map(p => [p.id, p.nome]));
    participantColors = new Map(participants.map((person, i) => [person.id, palette[i % palette.length]]));
    participantLegend.replaceChildren();
    participantFilter.replaceChildren(new Option('Todos', ''));
    participants.forEach(person => {
      const entry = document.createElement('span');
      entry.className = 'legend-item';
      entry.style.setProperty('--speaker-color', participantColors.get(person.id));
      const dot = document.createElement('i');
      dot.className = 'legend-dot';
      const id = document.createElement('b');
      id.textContent = person.id;
      entry.append(dot, id, document.createTextNode(` · ${person.nome}`));
      participantLegend.append(entry);
      if (person.id !== 'P00') {
        participantFilter.add(new Option(`${person.nome} (${person.id})`, person.id));
      }
    });
  }

  function renderRows() {
    const items = displayRows.filter(row => {
      const selectedParticipant = participantFilter.value;
      const query = normalizeText(searchInput.value.trim());
      return (!selectedParticipant || row.pid === selectedParticipant)
        && (!query || normalizeText(row.texto).includes(query));
    });
    const unit = groupingEnabled ? 'blocos' : 'falas';
    resultCount.textContent = `${items.length.toLocaleString('pt-BR')} de ${displayRows.length.toLocaleString('pt-BR')} ${unit}`;
    list.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'Nenhuma fala corresponde a esse filtro.';
      list.append(empty);
      return;
    }
    const fragment = document.createDocumentFragment();
    items.forEach(row => {
      const article = document.createElement('article');
      article.className = 'speech';
      if (selectedIds.has(row.id)) article.classList.add('is-selected');
      article.dataset.id = row.id;
      article.dataset.start = row.startMs;
      article.dataset.end = row.endMs;
      article.style.setProperty('--speaker-color', participantColors.get(row.pid) || palette[0]);
      article.tabIndex = 0;
      article.setAttribute('aria-label', `${participantNames.get(row.pid) || 'Pessoa não identificada'}: ${row.texto}. Clique no bloco para selecionar.`);

      const meta = document.createElement('div');
      meta.className = 'speaker-cell';
      const participant = document.createElement('span');
      participant.className = 'participant';
      participant.textContent = participantNames.get(row.pid) || 'Pessoa não identificada';
      const details = document.createElement('div');
      details.className = 'speaker-details';
      const participantId = document.createElement('span');
      participantId.className = 'participant-id';
      participantId.textContent = row.pid;
      const time = document.createElement('time');
      time.dateTime = `PT${(row.startMs / 1000).toFixed(3)}S`;
      time.textContent = `${formatCompactMs(row.startMs)}–${formatCompactMs(row.endMs)}`;
      time.title = `${formatMs(row.startMs)} – ${formatMs(row.endMs)}`;
      const confidence = document.createElement('span');
      confidence.className = 'speaker-confidence';
      confidence.textContent = `confiança ${row.confidence}%`;
      const segmentId = document.createElement('span');
      segmentId.className = 'speech-id';
      segmentId.textContent = row.sourceRows.length > 1 ? `${row.sourceRows.length} falas agrupadas` : row.id;
      segmentId.title = row.sourceRows.map(source => source.id).join(', ');
      details.append(participantId, confidence, time, segmentId);
      meta.append(participant, details);

      const text = document.createElement('p');
      text.className = 'speech-text';
      text.textContent = row.texto;

      const actions = document.createElement('div');
      actions.className = 'speech-actions';
      const playOnce = document.createElement('button');
      playOnce.type = 'button';
      playOnce.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
      playOnce.title = 'Toca só esta fala';
      playOnce.setAttribute('aria-label', `Reproduzir apenas a fala ${row.id}`);
      playOnce.addEventListener('click', () => playSegment(row, false));
      const playFromHere = document.createElement('button');
      playFromHere.type = 'button';
      playFromHere.innerHTML = '<svg class="continue-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5v14l9-7zM12 5v14l9-7z"/></svg>';
      playFromHere.title = 'Toca desta fala em diante';
      playFromHere.setAttribute('aria-label', `Reproduzir a partir da fala ${row.id}`);
      playFromHere.addEventListener('click', () => playSegment(row, true));
      actions.append(playOnce, playFromHere);

      const speechCell = document.createElement('div');
      speechCell.className = 'speech-cell';
      speechCell.append(text, actions);
      article.append(meta, speechCell);
      article.addEventListener('click', event => {
        if (event.target.closest('button')) return;
        toggleSelection(row, article);
      });
      article.addEventListener('keydown', event => {
        if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('button')) {
          event.preventDefault();
          toggleSelection(row, article);
        }
      });
      fragment.append(article);
    });
    list.append(fragment);
    const previousActiveId = activeId;
    activeId = null;
    setActive(previousActiveId, false);
    updateSelectionControls();
  }

  function toggleGroupingMode() {
    groupingEnabled = !groupingEnabled;
    displayRows = groupingEnabled
      ? groupConsecutiveRows(rows)
      : rows.map(row => ({...row, sourceRows: [row], idEnd: row.id}));
    selectedIds.clear();
    toggleGrouping?.setAttribute('aria-pressed', String(!groupingEnabled));
    if (toggleGrouping) toggleGrouping.textContent = groupingEnabled ? 'Desagrupar falas' : 'Agrupar falas';
    playerMessage.textContent = groupingEnabled
      ? 'Falas agrupadas em blocos próximos.'
      : 'Falas exibidas individualmente.';
    renderRows();
  }

  function toggleSelection(row, article) {
    if (selectedIds.has(row.id)) {
      selectedIds.delete(row.id);
      article.classList.remove('is-selected');
    } else {
      selectedIds.add(row.id);
      article.classList.add('is-selected');
    }
    updateSelectionControls();
  }

  function groupConsecutiveRows(sourceRows) {
    const groups = [];
    sourceRows.forEach(row => {
      const previous = groups[groups.length - 1];
      const gap = previous ? row.startMs - previous.endMs : Infinity;
      const joinedText = previous ? `${previous.texto.trim()} ${row.texto.trim()}`.replace(/\s+/g, ' ').trim() : '';
      const joinedDuration = previous ? row.endMs - previous.sourceRows[0].startMs : Infinity;
      if (previous && previous.pid === row.pid && gap >= -120 && gap <= 550
          && previous.sourceRows.length < 3 && joinedDuration <= 20_000 && joinedText.length <= 320) {
        previous.sourceRows.push(row);
        previous.endMs = Math.max(previous.endMs, row.endMs);
        previous.texto = joinedText;
        previous.idEnd = row.id;
        previous.posicao_1_fim_ms = row.posicao_1_fim_ms ?? row.posicao_1_fim ?? previous.posicao_1_fim_ms;
        previous.posicao_2_fim_ms = row.posicao_2_fim_ms ?? row.posicao_2_fim ?? previous.posicao_2_fim_ms;
        previous.confidence = Math.min(previous.confidence, row.confidence);
      } else {
        groups.push({...row, sourceRows: [row], idEnd: row.id});
      }
    });
    return groups.map(group => ({
      ...group,
      id: group.sourceRows.length > 1 ? `${group.sourceRows[0].id}–${group.idEnd}` : group.sourceRows[0].id,
      startMs: Math.min(...group.sourceRows.map(row => row.startMs)),
      endMs: Math.max(...group.sourceRows.map(row => row.endMs)),
    }));
  }

  function updateSelectionControls() {
    const count = selectedIds.size;
    if (selectionCount) selectionCount.textContent = `${count.toLocaleString('pt-BR')} ${count === 1 ? 'bloco selecionado' : 'blocos selecionados'}`;
    if (copySelection) copySelection.disabled = count === 0;
    if (clearSelection) clearSelection.disabled = count === 0;
  }

  function cancelSelection() {
    selectedIds.clear();
    document.querySelectorAll('.speech.is-selected').forEach(node => node.classList.remove('is-selected'));
    updateSelectionControls();
  }

  function citationText() {
    const selected = displayRows.map((row, index) => ({row, index})).filter(item => selectedIds.has(item.row.id));
    const groups = [];
    selected.forEach(({row, index}) => {
      const lastGroup = groups[groups.length - 1];
      if (lastGroup && lastGroup.lastIndex === index - 1) {
        lastGroup.rows.push(row);
        lastGroup.lastIndex = index;
      } else groups.push({rows: [row], firstIndex: index, lastIndex: index});
    });
    const excerpts = groups.map(group => {
      const runs = [];
      group.rows.forEach(row => {
        const lastRun = runs[runs.length - 1];
        if (lastRun && lastRun.pid === row.pid) {
          lastRun.text += ` ${row.texto}`;
          lastRun.endMs = row.endMs;
        } else runs.push({pid: row.pid, text: row.texto, startMs: row.startMs, endMs: row.endMs});
      });
      return runs.map(run => {
        const name = participantNames.get(run.pid) || 'Pessoa não identificada';
        const speaker = run.pid === 'P03' && page === 'reflexao' ? 'Iris' : name;
        return `“${run.text.trim()}” (${speaker.toLocaleUpperCase('pt-BR')}, [s. d.], ${formatMs(run.startMs)}–${formatMs(run.endMs)})`;
      }).join(' ');
    });
    return excerpts.join('\n\n');
  }

  async function copyCitations() {
    if (!selectedIds.size) return;
    const text = citationText();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const helper = document.createElement('textarea');
      helper.value = text;
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.append(helper);
      helper.select();
      document.execCommand('copy');
      helper.remove();
    }
    playerMessage.textContent = 'Trechos e referências copiados.';
  }

  function seekAndPlay(trackKey, localStartMs, localEndMs, row, continueAfter) {
    const track = config.tracks[trackKey];
    sourceSelect.value = trackKey;
    currentTrackKey = trackKey;
    stopAtTrackMs = continueAfter ? null : localEndMs;
    playerMessage.textContent = `${participantNames.get(row.pid) || 'Pessoa não identificada'} (${row.pid}) · ${row.id}`;
    const startPlayback = () => {
      player.currentTime = Math.max(0, localStartMs / 1000);
      setActive(row.id, true);
      player.play().catch(() => {
        playerMessage.textContent = 'O navegador bloqueou a reprodução. Pressione play no player.';
      });
    };
    const sameSource = player.dataset.src === track.src;
    if (sameSource && player.readyState >= 1) {
      startPlayback();
    } else {
      player.dataset.src = track.src;
      player.src = track.src;
      player.load();
      player.onloadedmetadata = () => {
        player.onloadedmetadata = null;
        startPlayback();
      };
    }
  }

  function playSegment(row, continueAfter) {
    const selected = sourceSelect.value;
    if (selected === 'posicao1') {
      if (row.posicao_1_inicio_ms == null || row.posicao_1_fim_ms == null) {
        playerMessage.textContent = 'Este trecho só existe na gravação Posição 2; troquei a fonte do áudio.';
        seekAndPlay('posicao2', row.posicao_2_inicio_ms ?? row.startMs,
          row.posicao_2_fim_ms ?? row.endMs, row, continueAfter);
        return;
      }
      seekAndPlay('posicao1', row.posicao_1_inicio_ms, row.posicao_1_fim_ms, row, continueAfter);
      return;
    }
    const start = selected === 'posicao2' ? (row.posicao_2_inicio_ms ?? row.startMs) : row.startMs;
    const end = selected === 'posicao2' ? (row.posicao_2_fim_ms ?? row.endMs) : row.endMs;
    seekAndPlay(selected, start, end, row, continueAfter);
  }

  function setActive(id, scroll) {
    const activeGroup = id && displayRows.find(group => group.sourceRows.some(row => row.id === id) || group.id === id);
    const displayId = activeGroup?.id || null;
    if (activeId === displayId) return;
    activeId = displayId;
    document.querySelectorAll('.speech.is-active').forEach(node => {
      node.classList.remove('is-active');
      node.removeAttribute('aria-current');
    });
    if (!displayId) return;
    const node = [...document.querySelectorAll('.speech')].find(item => item.dataset.id === displayId);
    if (!node) return;
    node.classList.add('is-active');
    node.setAttribute('aria-current', 'true');
    if (scroll) {
      const area = transcriptScroll;
      if (!area) return;
      const areaRect = area.getBoundingClientRect();
      const rowRect = node.getBoundingClientRect();
      const desiredTop = area.scrollTop + rowRect.top - areaRect.top + rowRect.height / 2 - area.clientHeight / 2;
      area.scrollTo({top: desiredTop, behavior: 'smooth'});
    }
  }

  function updateActiveSpeech() {
    const t = eventTimeMs();
    let low = 0;
    let high = rows.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (rows[middle].startMs <= t) low = middle + 1;
      else high = middle;
    }
    let found = null;
    for (let i = low - 1; i >= Math.max(0, low - 10); i -= 1) {
      if (rows[i].startMs <= t && t <= rows[i].endMs) {
        found = rows[i];
        break;
      }
    }
    setActive(found?.id || null, true);
    currentTime.textContent = formatMs(t);
    if (stopAtTrackMs != null && player.currentTime * 1000 >= stopAtTrackMs) {
      player.pause();
      stopAtTrackMs = null;
    }
  }

  function changeTrack() {
    const officialMs = eventTimeMs();
    const nextKey = sourceSelect.value;
    const next = config.tracks[nextKey];
    stopAtTrackMs = null;
    currentTrackKey = nextKey;
    player.dataset.src = next.src;
    player.src = next.src;
    player.load();
    player.onloadedmetadata = () => {
      player.onloadedmetadata = null;
      const local = officialMs - next.offsetMs;
      player.currentTime = Math.max(0, local / 1000);
      updateActiveSpeech();
      playerMessage.textContent = `Fonte selecionada: ${next.label}.`;
    };
  }

  async function init() {
    try {
      let transcript;
      let index;
      const bundled = window.CINEPET_TRANSCRIPTION_DATA;
      if (bundled?.page === page) {
        ({transcript, index} = bundled);
      } else {
        const [transcriptResponse, indexResponse] = await Promise.all([
          fetch(config.data), fetch(config.index),
        ]);
        if (!transcriptResponse.ok || !indexResponse.ok) throw new Error('Os arquivos de transcrição não foram carregados. Abra pela página inicial do site ou sirva a pasta por HTTP.');
        [transcript, index] = await Promise.all([
          transcriptResponse.json(), indexResponse.json(),
        ]);
      }
      renderLegend(index);
      rows = (transcript.falas || []).map(normalizeSegment)
        .sort((a, b) => a.startMs - b.startMs || a.endMs - b.endMs);
      displayRows = groupConsecutiveRows(rows);
      renderRows();
      if (sourceSelect.value && config.tracks[sourceSelect.value]) {
        const track = activeTrack();
        currentTrackKey = sourceSelect.value;
        player.src = track.src;
        player.dataset.src = track.src;
      }
      playerMessage.textContent = 'Use o player ou escolha uma opção de reprodução em uma fala.';
      updateActiveSpeech();
    } catch (error) {
      resultCount.textContent = 'Falha ao carregar a transcrição.';
      list.innerHTML = `<p class="empty-state">${escape(error.message)} Confira se a página está sendo servida por HTTP e se os arquivos da pasta dashboard estão presentes.</p>`;
    }
  }

  participantFilter.addEventListener('change', renderRows);
  searchInput.addEventListener('input', renderRows);
  sourceSelect.addEventListener('change', changeTrack);
  player.addEventListener('timeupdate', updateActiveSpeech);
  player.addEventListener('seeked', updateActiveSpeech);
  clearSelection?.addEventListener('click', cancelSelection);
  copySelection?.addEventListener('click', copyCitations);
  toggleGrouping?.addEventListener('click', toggleGroupingMode);
  init();
})();
