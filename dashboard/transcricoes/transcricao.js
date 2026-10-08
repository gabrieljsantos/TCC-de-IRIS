(() => {
  const page = document.body.dataset.page;
  const configs = {
    posicoes: {
      data: 'dados/perigo-historia-unica.json',
      index: 'dados/indice-perigo-historia-unica.json',
      tracks: {
        posicao2: { src: '../media/posicao-2.mp3', offsetMs: 0, label: 'Posição 2' },
        posicao1: { src: '../media/posicao-1.mp3', offsetMs: 142600, label: 'Posição 1' },
      },
    },
    reflexao: {
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
  let rows = [];
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

  function visibleRows() {
    const pid = participantFilter.value;
    const query = normalizeText(searchInput.value.trim());
    return rows.filter(row => (!pid || row.pid === pid)
      && (!query || normalizeText(row.texto).includes(query)));
  }

  function renderRows() {
    const items = visibleRows();
    resultCount.textContent = `${items.length.toLocaleString('pt-BR')} de ${rows.length.toLocaleString('pt-BR')} falas`;
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
      article.dataset.id = row.id;
      article.dataset.start = row.startMs;
      article.dataset.end = row.endMs;
      article.style.setProperty('--speaker-color', participantColors.get(row.pid) || palette[0]);

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
      segmentId.textContent = row.id;
      segmentId.title = `ID da fala: ${row.id}`;
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
      fragment.append(article);
    });
    list.append(fragment);
    setActive(activeId, false);
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
    if (activeId === id) return;
    activeId = id;
    document.querySelectorAll('.speech.is-active').forEach(node => {
      node.classList.remove('is-active');
      node.removeAttribute('aria-current');
    });
    if (!id) return;
    const node = [...document.querySelectorAll('.speech')].find(item => item.dataset.id === id);
    if (!node) return;
    node.classList.add('is-active');
    node.setAttribute('aria-current', 'true');
    if (scroll) {
      const panel = document.querySelector('.player-panel');
      const panelBottom = panel ? Math.max(0, panel.getBoundingClientRect().bottom) : 0;
      const visibleMiddle = panelBottom + Math.max(0, window.innerHeight - panelBottom) / 2;
      const rowMiddle = node.getBoundingClientRect().top + node.getBoundingClientRect().height / 2;
      window.scrollBy({ top: rowMiddle - visibleMiddle, behavior: 'smooth' });
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
      const [transcriptResponse, indexResponse] = await Promise.all([
        fetch(config.data), fetch(config.index),
      ]);
      if (!transcriptResponse.ok || !indexResponse.ok) throw new Error('Não foi possível abrir os arquivos de transcrição e participantes.');
      const [transcript, index] = await Promise.all([
        transcriptResponse.json(), indexResponse.json(),
      ]);
      renderLegend(index);
      rows = (transcript.falas || []).map(normalizeSegment)
        .sort((a, b) => a.startMs - b.startMs || a.endMs - b.endMs);
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
  init();
})();
