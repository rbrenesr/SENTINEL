(function (root) {
  'use strict';
  const workflowURL = 'https://github.com/rbrenesr/SENTINEL/actions/workflows/update-news.yml';
  const apiURL = 'https://api.github.com/repos/rbrenesr/SENTINEL/actions/workflows/update-news.yml';
  const runBase = 'https://github.com/rbrenesr/SENTINEL/actions/runs/';
  const headers = {Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10'};
  const runURL = id => /^\d+$/.test(String(id)) ? runBase + id : null;
  function freshness(timestamp, now = Date.now()) {
    const date = timestamp ? new Date(timestamp).getTime() : NaN;
    if (!Number.isFinite(date) || date > now + 300000) return {delayed: true, ageMinutes: null};
    const ageMinutes = Math.max(0, Math.floor((now - date) / 60000));
    return {delayed: ageMinutes > 45, ageMinutes};
  }
  function runLabel(run) {
    if (!run) return 'Sin información de ejecuciones';
    if (run.status !== 'completed') return ['queued', 'waiting', 'pending', 'requested'].includes(run.status) ?
      'Recopilación en espera de GitHub' : 'Recopilación en curso';
    return {success: 'Ejecución completada', failure: 'Falló la actualización', cancelled: 'Actualización cancelada',
      timed_out: 'La actualización excedió el tiempo disponible', skipped: 'Comprobación omitida'}[run.conclusion] || 'Ejecución finalizada';
  }
  function failure(response) {
    const error = new Error(response.status === 401 ? 'authorization' : response.status === 403 || response.status === 429 ? 'permission_or_limit' : 'github_unavailable');
    error.status = response.status;
    const reset = Number(response.headers?.get('x-ratelimit-reset')) * 1000;
    error.retryAt = response.headers?.get('x-ratelimit-remaining') === '0' && reset > Date.now() ? reset : Date.now() + 300000;
    return error;
  }
  async function readRuns(fetcher = root.fetch.bind(root)) {
    const response = await fetcher(apiURL + '/runs?branch=main&per_page=10', {
      headers, cache: 'no-store', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(12000)
    });
    if (!response.ok) throw failure(response);
    const result = await response.json();
    if (!Array.isArray(result.workflow_runs)) throw Error('invalid_status');
    return result.workflow_runs.filter(run => run.head_branch === 'main' && runURL(run.id));
  }
  async function dispatchCollection(token, requestId, fetcher = root.fetch.bind(root)) {
    if (!/^github_pat_[A-Za-z0-9_]{20,}$/.test(token || '')) throw Error('fine_grained_token_required');
    if (!/^[a-zA-Z0-9-]{16,64}$/.test(requestId || '')) throw Error('invalid_request');
    let response;
    try {
      response = await fetcher(apiURL + '/dispatches', {
        method: 'POST', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer',
        headers: {...headers, 'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
        body: JSON.stringify({ref: 'main', inputs: {request_id: requestId}}), signal: AbortSignal.timeout(20000)
      });
    } finally { token = ''; }
    if (!response.ok) throw failure(response);
    if (response.status === 204) return {requestId, id: null};
    const result = await response.json();
    return {requestId, id: runURL(result.workflow_run_id) ? String(result.workflow_run_id) : null};
  }
  function mount() {
    const $ = id => document.getElementById(id);
    if (!$('forceCollect') || !$('collectionDialog')) return;
    let snapshot = null, runs = [], pending = null, busy = false, timer = null, retryAt = 0, lastRead = 0;
    let observedRun = null;
    const dialog = $('collectionDialog'), tokenField = $('collectionToken');
    const status = text => { $('collectionStatus').textContent = text; };
    const clearToken = () => { tokenField.value = ''; };
    function paint() {
      const age = freshness(snapshot?.updatedAt);
      $('collectionAge').textContent = age.ageMinutes === null ? 'Fecha de recopilación no disponible.' :
        `Datos recopilados hace ${age.ageMinutes < 60 ? age.ageMinutes + ' min' : Math.floor(age.ageMinutes / 60) + ' h ' + age.ageMinutes % 60 + ' min'}.`;
      $('collectionAge').classList.toggle('bad', age.delayed);
      const run = pending?.id ? runs.find(run => String(run.id) === String(pending.id)) : runs[0];
      $('automationStatus').textContent = run ? runLabel(run) : 'Comprobando la actualización automática…';
      const url = runURL(run?.id);
      $('automationRun').hidden = !url;
      if (url) $('automationRun').href = url;
      $('forceCollect').disabled = busy || Boolean(pending);
      $('cancelCollectionTracking').hidden = !pending;
      $('collectionWarning').hidden = !age.delayed;
      if (age.delayed) $('collectionWarning').textContent = 'La recopilación está retrasada. Podés iniciar una nueva y consultar el estado de GitHub.';
    }
    function schedule() {
      clearTimeout(timer);
      const active = pending || runs.some(run => run.status !== 'completed');
      timer = setTimeout(() => check(), Math.max(active ? 20000 : 300000, retryAt - Date.now()));
    }
    function acceptSnapshot(detail) {
      snapshot = detail;
      if (pending && detail.collection?.outcome !== 'error' && detail.updatedAt !== pending.previousTimestamp &&
          ((detail.collection?.runId && String(detail.collection.runId) === String(pending.id)) ||
           (pending.requestId && detail.collection?.requestId === pending.requestId))) {
        status(detail.collection.outcome === 'partial' ? 'Nueva recopilación publicada con cobertura parcial.' : 'Nueva recopilación publicada.');
        pending = null;
      }
      paint();
    }
    async function check(force = false) {
      if (document.hidden || Date.now() < retryAt || (!force && Date.now() - lastRead < 15000)) { schedule(); return; }
      lastRead = Date.now();
      try {
        runs = await readRuns(); retryAt = 0;
        if (pending) {
          const match = pending.id ? runs.find(run => String(run.id) === String(pending.id)) :
            runs.find(run => run.event === 'workflow_dispatch' && (pending.requestId ?
              run.display_title === 'Recopilación manual · ' + pending.requestId : new Date(run.created_at).getTime() >= pending.startedAt - 5000));
          if (match) {
            pending.id = String(match.id);
            status(runLabel(match));
            if (match.status === 'completed') {
              if (match.conclusion === 'success') {
                pending.completed = true;
                status('Recopilación terminada. Comprobando la nueva publicación…');
                window.dispatchEvent(new CustomEvent('sentinel:reload'));
              } else { pending = null; }
            }
          }
          if (pending && Date.now() - pending.startedAt > 600000) {
            status(pending.completed ? 'GitHub terminó. La nueva publicación todavía no pudo confirmarse; usá «Revisar publicación».' :
              'La solicitud sigue sin confirmarse. Consultá GitHub antes de volver a solicitarla.');
            pending = null;
          }
        }
        const latest = runs[0];
        if (latest?.status === 'completed' && latest.id !== observedRun) {
          observedRun = latest.id;
          if (latest.conclusion === 'success') window.dispatchEvent(new CustomEvent('sentinel:reload'));
        }
        paint();
      } catch (error) {
        retryAt = error.retryAt || Date.now() + 300000;
        $('automationStatus').textContent = 'No se pudo consultar GitHub. La fecha de los datos sigue disponible.';
      } finally { schedule(); }
    }
    $('forceCollect').onclick = () => { clearToken(); $('collectionError').textContent = ''; dialog.showModal(); };
    $('closeCollection').onclick = () => dialog.close();
    dialog.addEventListener('close', clearToken);
    dialog.addEventListener('cancel', clearToken);
    $('githubCollection').href = workflowURL;
    $('githubCollection').onclick = () => {
      pending = {startedAt: Date.now(), previousTimestamp: snapshot?.updatedAt};
      status('En GitHub elegí «Run workflow», rama main, y confirmá la ejecución. Al volver comprobaremos el resultado.');
      dialog.close(); paint(); schedule();
    };
    $('cancelCollectionTracking').onclick = () => { pending = null; status('Seguimiento detenido. La ejecución en GitHub continúa si ya fue iniciada.'); paint(); schedule(); };
    $('collectionForm').onsubmit = async event => {
      event.preventDefault();
      if (busy || pending) return;
      let token = tokenField.value.trim(); clearToken();
      busy = true; $('dispatchCollection').disabled = true; $('collectionError').textContent = '';
      try {
        const requestId = crypto.randomUUID();
        const result = await dispatchCollection(token, requestId);
        pending = {...result, startedAt: Date.now(), previousTimestamp: snapshot?.updatedAt};
        status('Solicitud autorizada. Esperando que GitHub inicie la recopilación…');
        dialog.close(); lastRead = 0; await check(true);
      } catch (error) {
        $('collectionError').textContent = error.message === 'fine_grained_token_required' ?
          'Usá un token de acceso detallado de GitHub limitado a SENTINEL, con permiso Actions: escritura.' :
          error.status === 401 || error.status === 403 ? 'GitHub no autorizó la solicitud. Revisá la vigencia del token, el repositorio y el permiso Actions: escritura.' :
          'No se pudo confirmar la solicitud. Consultá GitHub antes de reintentar, porque podría haberse recibido.';
      } finally { token = ''; clearToken(); busy = false; $('dispatchCollection').disabled = false; paint(); }
    };
    window.addEventListener('sentinel:data', event => acceptSnapshot(event.detail));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { paint(); check(); } });
    setInterval(paint, 60000);
    paint(); check();
  }
  const api = {workflowURL, apiURL, freshness, runLabel, readRuns, dispatchCollection, runURL};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else {
    root.SentinelUpdates = api;
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
    else mount();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
