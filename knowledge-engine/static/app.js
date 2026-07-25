const $ = (selector) => document.querySelector(selector);
const state = { concepts: [], activeCategory: '', activeConcept: null };

const categoryColors = {
  '人工智能': '#6366f1', '计算机科学': '#3b82f6', '生物学': '#10b981',
  '物理学': '#f59e0b', '天文学': '#8b5cf6', '数学': '#ec4899', '哲学': '#f97316'
};

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '请求失败');
  return body;
}

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function showToast(message, isError = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast visible ${isError ? 'error' : ''}`;
  window.setTimeout(() => { toast.className = 'toast'; }, 2800);
}

async function loadStats() {
  const data = await api('/api/stats');
  $('#stat-concepts').textContent = data.concepts;
  $('#stat-relations').textContent = data.relations;
  $('#stat-evidence').textContent = data.evidence;
  $('#stat-hypotheses').textContent = data.hypotheses;
}

function renderConceptList(items) {
  const list = $('#concept-list');
  if (!items.length) { list.innerHTML = '<div class="no-results">没有找到匹配的概念<br><small>试试其他关键词，或添加一个新概念</small></div>'; return; }
  list.innerHTML = items.map((item) => `
    <button class="concept-item ${state.activeConcept?.id === item.id ? 'selected' : ''}" data-id="${item.id}">
      <span class="concept-avatar" style="--accent:${categoryColors[item.category] || '#64748b'}">${escapeHTML(item.name.slice(0, 1))}</span>
      <span class="concept-copy"><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.category || '未分类')}</small></span>
      ${item.score ? `<span class="score">${Math.round(item.score * 100)}%</span>` : '<span class="chevron">›</span>'}
    </button>`).join('');
  list.querySelectorAll('.concept-item').forEach((button) => button.addEventListener('click', () => selectConcept(button.dataset.id)));
}

async function loadConcepts() {
  const query = $('#search-input').value.trim();
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (state.activeCategory) params.set('category', state.activeCategory);
  try {
    const data = await api(`/api/concepts?${params}`);
    state.concepts = data.items;
    renderConceptList(data.items);
  } catch (error) { showToast(error.message, true); }
}

function relationTone(type) {
  if (['supports', 'is_a', 'part_of'].includes(type)) return 'positive';
  if (type === 'contradicts') return 'negative';
  return 'neutral';
}

async function selectConcept(id) {
  try {
    state.activeConcept = await api(`/api/concepts/${id}`);
    renderConceptList(state.concepts);
    const [relations, evidence, graphData] = await Promise.all([
      api(`/api/relations?concept_id=${id}`), api(`/api/evidence?concept_id=${id}`), api(`/api/graph?concept_id=${id}`)
    ]);
    const c = state.activeConcept;
    $('#empty-state').classList.add('hidden');
    const detail = $('#concept-detail'); detail.classList.remove('hidden');
    detail.innerHTML = `
      <div class="detail-header"><div><div class="breadcrumb">ATLAS / ${escapeHTML(c.category)}</div><h2>${escapeHTML(c.name)}</h2><p>${escapeHTML(c.description)}</p></div><span class="big-avatar" style="--accent:${categoryColors[c.category] || '#64748b'}">${escapeHTML(c.name.slice(0, 1))}</span></div>
      <div class="detail-meta"><span class="pill" style="--accent:${categoryColors[c.category] || '#64748b'}">${escapeHTML(c.category)}</span>${(c.tags || []).map((tag) => `<span class="tag">#${escapeHTML(tag)}</span>`).join('')}<span class="source">来源：${escapeHTML(c.source || '社区知识')}</span></div>
      <div class="graph-wrap"><div class="section-label"><span>RELATIONSHIP MAP</span><span class="legend"><i></i>当前概念　<i></i>关联概念</span></div><div class="graph-canvas">${graphData.svg || '<div class="no-results">暂无关系</div>'}</div></div>
      <div class="evidence-section"><div class="section-label"><span>EVIDENCE & CONNECTIONS</span><span>${relations.items.length} 个关系 · ${evidence.items.length} 条证据</span></div>
        <div class="connection-list">${relations.items.map((r) => `<div class="connection"><span class="connection-dot ${relationTone(r.relation_type)}"></span><div><strong>${escapeHTML(r.source_id === c.id ? r.target_name : r.source_name)}</strong><span class="relation-type">${escapeHTML(r.relation_type)}</span><p>${escapeHTML(r.evidence || '暂无关系说明')}</p></div><span class="confidence">${Math.round(r.confidence * 100)}%</span></div>`).join('') || '<div class="no-results">还没有关联关系</div>'}</div>
        ${evidence.items.length ? `<div class="evidence-list">${evidence.items.map((e) => `<div class="evidence"><span>“</span><p>${escapeHTML(e.content)}<small>${escapeHTML(e.source_title || '未注明来源')}</small></p></div>`).join('')}</div>` : ''}
      </div>`;
  } catch (error) { showToast(error.message, true); }
}

function renderHypothesisResult(result) {
  const summary = result.evidence_summary || {};
  const labels = { supports: ['有支持证据', '当前知识网络中找到了一些支持这个假设的线索。'], contradicts: ['存在反对证据', '当前知识网络中发现了与这个假设相冲突的线索。'], inconclusive: ['证据尚不充分', '现有知识网络还不足以得出明确结论。'], unknown: ['尚未建立连接', '知识库里还没有找到与这个假设相关的概念。'] };
  const [title, desc] = labels[result.result] || labels.unknown;
  const level = summary.overall_level || 'none';
  const levelLabel = { strong: '强证据', moderate: '中等证据', weak: '弱证据', none: '无直接证据' }[level] || '未知';
  const box = $('#hypothesis-result'); box.className = `hypothesis-result ${result.result}`;
  box.innerHTML = `<div class="verdict"><span>${result.result === 'supports' ? '↗' : result.result === 'contradicts' ? '↘' : '?'}</span><div><strong>${title}</strong><small>${desc}</small></div><b>${Math.round((result.confidence || 0) * 100)}%</b></div><div class="evidence-level"><span>证据强度</span><strong class="level-${level}">${levelLabel}</strong></div><div class="result-evidence">${(summary.supports || []).slice(0, 3).map((item) => `<div><i class="positive">+</i><span>${escapeHTML(item.concept)} · ${escapeHTML(item.relation)} <em class="mini-level ${item.level}">${item.level}</em><small>${escapeHTML(item.evidence || '相关关系')}</small></span></div>`).join('')}${(summary.contradicts || []).slice(0, 3).map((item) => `<div><i class="negative">−</i><span>${escapeHTML(item.concept)} · ${escapeHTML(item.relation)} <em class="mini-level ${item.level}">${item.level}</em><small>${escapeHTML(item.evidence || '矛盾关系')}</small></span></div>`).join('')}</div>${(summary.counterexamples || []).length ? `<div class="analysis-block"><strong>反例与冲突</strong>${summary.counterexamples.map((item) => `<p>↯ ${escapeHTML(item.concept_a)} ${escapeHTML(item.relation)} ${escapeHTML(item.concept_b)}：${escapeHTML(item.evidence)}</p>`).join('')}</div>` : ''}${(summary.open_questions || []).length ? `<div class="analysis-block open"><strong>开放问题</strong>${summary.open_questions.slice(0, 3).map((item) => `<p>？${escapeHTML(item.question)}</p>`).join('')}</div>` : ''}`;
  box.classList.remove('hidden');
}

async function submitHypothesis(event) {
  event.preventDefault();
  const input = $('#hypothesis-input'); const button = event.target.querySelector('button');
  button.disabled = true; button.innerHTML = '分析中…';
  try {
    const result = await api('/api/hypothesis', { method: 'POST', body: JSON.stringify({ statement: input.value }) });
    renderHypothesisResult(result); input.value = ''; await Promise.all([loadStats(), loadHypothesisHistory()]);
  } catch (error) { showToast(error.message, true); }
  finally { button.disabled = false; button.innerHTML = '开始验证 <span>→</span>'; }
}

async function loadHypothesisHistory() {
  const data = await api('/api/hypotheses');
  const history = $('#hypothesis-history');
  if (!data.items.length) { history.innerHTML = '<div class="no-results">还没有假设记录<br><small>提出第一个问题吧</small></div>'; return; }
  history.innerHTML = data.items.slice(0, 5).map((item) => `<button class="history-item" title="${escapeHTML(item.statement)}"><span class="history-status ${item.result}">${item.result === 'supports' ? '↗' : item.result === 'contradicts' ? '↘' : '?'}</span><span>${escapeHTML(item.statement)}</span><b>${Math.round(item.confidence * 100)}%</b></button>`).join('');
}

async function createConcept(event) {
  event.preventDefault();
  const form = event.target; const data = Object.fromEntries(new FormData(form));
  data.tags = data.tags ? data.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  try { const concept = await api('/api/concepts', { method: 'POST', body: JSON.stringify(data) }); form.closest('dialog').close(); form.reset(); showToast('概念已加入 Atlas'); await Promise.all([loadStats(), loadConcepts()]); await selectConcept(concept.id); }
  catch (error) { showToast(error.message, true); }
}

function renderPaths(paths) {
  const box = $('#paths-result');
  if (!paths.length) { box.innerHTML = '<div class="no-results">当前证据不足以生成研究路径</div>'; box.className = 'paths-result'; return; }
  box.className = 'paths-result';
  box.innerHTML = `<div class="paths-head"><strong>选择一条研究路径继续</strong><span>人在环决策</span></div>${paths.map((path) => `<div class="path-card ${path.is_selected ? 'selected' : ''}"><div class="path-card-copy"><strong>${escapeHTML(path.path_label)}</strong><p>${escapeHTML(path.description)}</p><div class="path-tags">${(path.concept_names || []).slice(0, 5).map((name) => `<span>${escapeHTML(name)}</span>`).join('')}</div></div><button class="path-select" data-path-id="${path.id}">${path.is_selected ? '已选择' : '选择路径 →'}</button></div>`).join('')}`;
  box.querySelectorAll('.path-select').forEach((button) => button.addEventListener('click', async () => {
    const note = window.prompt('为什么选择这条路径？（可选）', '') || '';
    try { await api('/api/paths/select', { method: 'POST', body: JSON.stringify({ path_id: button.dataset.pathId, note }) }); showToast('研究路径已记录'); button.textContent = '已选择'; button.closest('.path-card').classList.add('selected'); }
    catch (error) { showToast(error.message, true); }
  }));
}

async function generatePaths() {
  const statement = $('#hypothesis-input').value.trim();
  if (!statement) { showToast('请先输入一个假设', true); return; }
  const button = $('#path-btn'); button.disabled = true; button.textContent = '生成中…';
  try { const data = await api('/api/hypothesis/paths', { method: 'POST', body: JSON.stringify({ statement }) }); renderPaths(data.paths || []); }
  catch (error) { showToast(error.message, true); }
  finally { button.disabled = false; button.textContent = '生成研究路径'; }
}

async function loadPapers() {
  const query = $('#paper-search-input').value.trim();
  try { const data = await api(`/api/papers${query ? `?q=${encodeURIComponent(query)}` : ''}`); const list = $('#paper-list'); if (!data.items.length) { list.innerHTML = '<div class="no-results">还没有收藏论文<br><small>可以导入 BibTeX，或搜索 arXiv</small></div>'; return; } list.innerHTML = data.items.map((paper) => `<article class="paper-card"><div class="paper-year">${paper.year || '—'}</div><div class="paper-copy"><strong>${escapeHTML(paper.title)}</strong><p>${escapeHTML((paper.authors || []).slice(0, 3).join(', '))}${(paper.authors || []).length > 3 ? ' 等' : ''}</p><small>${escapeHTML(paper.venue || '未注明来源')}${paper.doi ? ` · DOI: ${escapeHTML(paper.doi)}` : ''}${paper.arxiv_id ? ` · arXiv: ${escapeHTML(paper.arxiv_id)}` : ''}</small></div><a href="${escapeHTML(paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '#'))}" target="_blank" class="paper-link">↗</a></article>`).join(''); }
  catch (error) { showToast(error.message, true); }
}

async function importBibtex(event) {
  event.preventDefault(); const form = event.target; const data = Object.fromEntries(new FormData(form));
  try { const result = await api('/api/papers/import-bibtex', { method: 'POST', body: JSON.stringify(data) }); form.closest('dialog').close(); form.reset(); showToast(`已导入 ${result.total} 篇论文`); await loadPapers(); await loadStats(); }
  catch (error) { showToast(error.message, true); }
}

async function searchArxiv(event) {
  event.preventDefault(); const form = event.target; const query = new FormData(form).get('query'); const preview = $('#arxiv-preview');
  try { const data = await api(`/api/arxiv/search?q=${encodeURIComponent(query)}`); if (!data.items?.length) { preview.innerHTML = '<div class="no-results">没有找到论文，或网络暂不可用</div>'; } else { preview.className = 'arxiv-preview'; preview.innerHTML = data.items.slice(0, 5).map((item) => `<div class="arxiv-item"><div><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.arxiv_id)} · ${escapeHTML(item.authors.slice(0, 2).join(', '))}</small></div><button class="import-arxiv" data-id="${escapeHTML(item.arxiv_id)}">导入</button></div>`).join(''); preview.querySelectorAll('.import-arxiv').forEach((button) => button.addEventListener('click', async () => { try { await api('/api/arxiv/import', { method: 'POST', body: JSON.stringify({ arxiv_id: button.dataset.id }) }); showToast('arXiv 论文已导入'); await loadPapers(); await loadStats(); } catch (error) { showToast(error.message, true); } })); } }
  catch (error) { preview.innerHTML = `<div class="no-results">网络请求失败：${escapeHTML(error.message)}</div>`; preview.className = 'arxiv-preview'; }
}

function setup() {
  $('#search-input').addEventListener('input', loadConcepts);
  document.addEventListener('keydown', (event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'k') { event.preventDefault(); $('#search-input').focus(); } });
  $('#category-filters').addEventListener('click', (event) => { const button = event.target.closest('.filter'); if (!button) return; state.activeCategory = button.dataset.category; document.querySelectorAll('.filter').forEach((item) => item.classList.toggle('active', item === button)); loadConcepts(); });
  $('#hypothesis-form').addEventListener('submit', submitHypothesis);
  $('#path-btn').addEventListener('click', generatePaths);
  $('#concept-form').addEventListener('submit', createConcept);
  $('#new-concept-btn').addEventListener('click', () => $('#concept-dialog').showModal());
  $('#refresh-btn').addEventListener('click', () => Promise.all([loadStats(), loadConcepts(), loadHypothesisHistory(), loadPapers()]));
  $('#open-global-graph').addEventListener('click', async () => { try { const data = await api('/api/graph'); const win = window.open('', '_blank', 'width=780,height=650'); win.document.write(`<title>Atlas · 全局知识图谱</title><body style="margin:20px;background:#f1f5f9;font-family:sans-serif"><h2>Atlas 全局知识图谱</h2>${data.svg}</body>`); } catch (error) { showToast(error.message, true); } });
  $('#bibtex-btn').addEventListener('click', () => $('#bibtex-dialog').showModal());
  $('#bibtex-form').addEventListener('submit', importBibtex);
  $('#arxiv-btn').addEventListener('click', () => $('#arxiv-dialog').showModal());
  $('#arxiv-form').addEventListener('submit', searchArxiv);
  $('#paper-search-input').addEventListener('input', loadPapers);
  loadStats(); loadConcepts(); loadHypothesisHistory(); loadPapers();
}

document.addEventListener('DOMContentLoaded', setup);