const $ = (selector) => document.querySelector(selector);

const state = {
  activeView: 'explore',
  concepts: [],
  categories: [],
  activeCategory: '',
  activeConcept: null,
  paperMode: 'metadata',
  lastStatement: '',
  lastHypothesisId: '',
  editingConceptId: '',
  conceptRequest: null,
  paperRequest: null,
  issues: [],
  activeIssueId: '',
  pendingRequests: 0,
  connectionFailure: false,
};

const categoryColors = {
  '人工智能': '#3d63dd', '计算机科学': '#187c78', '生物学': '#28834f',
  '物理学': '#bd6b22', '天文学': '#7158a5', '数学': '#b34366', '哲学': '#6c6670',
  '认知科学': '#7b56a6', '科学发现': '#147f74', '科学哲学': '#9b6824',
};

const relationLabels = {
  causes: '导致', contradicts: '矛盾', supports: '支持', is_a: '属于', part_of: '组成部分',
  example: '示例', related_to: '相关', depends_on: '依赖',
};

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function safeURL(value, fallback = '#') {
  if (!value) return fallback;
  if (!/^https?:\/\//i.test(String(value).trim())) return fallback;
  try {
    const url = new URL(value, window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : fallback;
  } catch (_) {
    return fallback;
  }
}

function setConnection(mode, label) {
  const box = $('#connection-status');
  box.className = `connection ${mode}`;
  box.querySelector('span').textContent = label;
}

async function api(path, options = {}) {
  if (state.pendingRequests === 0) state.connectionFailure = false;
  state.pendingRequests += 1;
  setConnection('busy', '正在同步');
  try {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `请求失败 (${response.status})`);
    return body;
  } catch (error) {
    if (error.name !== 'AbortError') state.connectionFailure = true;
    throw error;
  } finally {
    state.pendingRequests -= 1;
    if (state.pendingRequests === 0) {
      setConnection(state.connectionFailure ? 'error' : 'connected', state.connectionFailure ? '连接异常' : '本地知识库已连接');
    }
  }
}

function showToast(message, isError = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast visible ${isError ? 'error' : ''}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { toast.className = 'toast'; }, 2800);
}

function debounce(fn, delay = 220) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}

function switchView(view) {
  state.activeView = view;
  document.querySelectorAll('.view-tab').forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('[data-view-panel]').forEach((panel) => {
    const active = panel.dataset.viewPanel === view;
    panel.hidden = !active;
    panel.classList.toggle('active', active);
  });
  window.history.replaceState(null, '', `#${view}`);
}

async function loadStats() {
  const data = await api('/api/stats');
  $('#stat-concepts').textContent = data.concepts;
  $('#stat-relations').textContent = data.relations;
  $('#stat-evidence').textContent = data.evidence;
  $('#stat-hypotheses').textContent = data.hypotheses;
  state.categories = data.categories || [];
  renderCategoryFilters();
}

function renderCategoryFilters() {
  const row = $('#category-filters');
  const categories = [{ category: '', label: '全部' }, ...state.categories.map((item) => ({ category: item.category, label: item.category }))];
  row.innerHTML = categories.map((item) => `<button class="filter ${state.activeCategory === item.category ? 'active' : ''}" data-category="${escapeHTML(item.category)}">${escapeHTML(item.label)}</button>`).join('');
}

function renderConceptList(items, total) {
  const list = $('#concept-list');
  $('#concept-result-count').textContent = `${total} 个概念`;
  if (!items.length) {
    list.innerHTML = '<div class="no-results"><strong>没有匹配概念</strong><span>调整关键词或领域筛选</span></div>';
    return;
  }
  list.innerHTML = items.map((item) => {
    const color = categoryColors[item.category] || '#5f6b76';
    return `<button class="concept-item ${state.activeConcept?.id === item.id ? 'selected' : ''}" data-id="${escapeHTML(item.id)}" style="--accent:${color}">
      <span class="concept-avatar">${escapeHTML(item.name.slice(0, 1))}</span>
      <span class="concept-copy"><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.category || '未分类')}</small></span>
      ${item.score != null ? `<span class="score">${Math.round(item.score * 1000) / 10}</span>` : '<span class="chevron">›</span>'}
    </button>`;
  }).join('');
  list.querySelectorAll('.concept-item').forEach((button) => button.addEventListener('click', () => selectConcept(button.dataset.id)));
}

async function loadConcepts() {
  if (state.conceptRequest) state.conceptRequest.abort();
  state.conceptRequest = new AbortController();
  const query = $('#search-input').value.trim();
  const params = new URLSearchParams({ limit: '100' });
  if (query) params.set('q', query);
  if (state.activeCategory) params.set('category', state.activeCategory);
  try {
    const data = await api(`/api/concepts?${params}`, { signal: state.conceptRequest.signal });
    state.concepts = data.items;
    renderConceptList(data.items, data.total);
  } catch (error) {
    if (error.name !== 'AbortError') showToast(error.message, true);
  }
}

const positionLabels = { supports: '支持能力', challenges: '挑战主张', qualifies: '限定条件' };
const stanceLabels = { supports: '支持', challenges: '反对', limits: '限制', context: '背景' };

function renderIssueList() {
  const list = $('#issue-list');
  $('#issue-count').textContent = state.issues.length;
  if (!state.issues.length) {
    list.innerHTML = '<div class="no-results"><strong>暂无策展议题</strong><span>议题会把竞争命题与证据组织在一起</span></div>';
    return;
  }
  list.innerHTML = state.issues.map((issue) => `<button class="issue-item ${state.activeIssueId === issue.id ? 'selected' : ''}" data-id="${escapeHTML(issue.id)}">
    <span>${escapeHTML(issue.status === 'open' ? '持续研究' : '已归档')}</span>
    <strong>${escapeHTML(issue.title)}</strong>
    <small>${issue.claim_count} 条命题 · ${issue.concept_count} 个概念</small>
  </button>`).join('');
  list.querySelectorAll('.issue-item').forEach((button) => button.addEventListener('click', () => selectIssue(button.dataset.id)));
}

async function loadIssues() {
  const data = await api('/api/issues');
  state.issues = data.items || [];
  renderIssueList();
  if (state.issues.length && !state.activeIssueId) await selectIssue(state.issues[0].id);
}

async function selectIssue(issueId) {
  state.activeIssueId = issueId;
  renderIssueList();
  const detail = $('#issue-detail');
  detail.innerHTML = '<div class="loading">正在整理命题与证据…</div>';
  try {
    const issue = await api(`/api/issues/${encodeURIComponent(issueId)}`);
    const concepts = (issue.concepts || []).map((concept) => `<button class="issue-concept" data-concept-id="${escapeHTML(concept.id)}"><span>${escapeHTML(concept.role)}</span>${escapeHTML(concept.name)}</button>`).join('');
    const claims = (issue.claims || []).map((claim, index) => {
      const evidence = (claim.evidence || []).map((item) => {
        const url = safeURL(item.source_url, '');
        return `<div class="claim-source ${escapeHTML(item.stance)}"><span>${escapeHTML(stanceLabels[item.stance] || item.stance)}</span><div><p>${escapeHTML(item.summary)}</p><small>${escapeHTML(item.source_title || '专题分析')}${url ? ` · <a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">原始来源 ↗</a>` : ''}</small></div></div>`;
      }).join('');
      return `<article class="issue-claim ${escapeHTML(claim.position)}"><header><span>命题 ${index + 1}</span><b>${escapeHTML(positionLabels[claim.position] || claim.position)}</b><strong>${Math.round(claim.confidence * 100)}%</strong></header><h3>${escapeHTML(claim.statement)}</h3><p>${escapeHTML(claim.assessment)}</p><div class="claim-sources">${evidence}</div></article>`;
    }).join('');
    detail.innerHTML = `<header class="issue-hero"><p class="eyebrow">OPEN QUESTION · ${escapeHTML(issue.status === 'open' ? '持续研究' : '已归档')}</p><h2>${escapeHTML(issue.title)}</h2><p>${escapeHTML(issue.question)}</p></header>
      <section class="issue-assessment"><span>当前判断</span><p>${escapeHTML(issue.current_assessment)}</p></section>
      <section class="issue-summary"><p>${escapeHTML(issue.summary)}</p><div class="issue-concepts">${concepts}</div></section>
      <section class="issue-claims"><div class="section-head"><h4>竞争命题与证据</h4><span>${(issue.claims || []).length} 条命题</span></div>${claims}</section>`;
    detail.querySelectorAll('.issue-concept').forEach((button) => button.addEventListener('click', async () => {
      switchView('explore');
      await selectConcept(button.dataset.conceptId);
    }));
  } catch (error) {
    detail.innerHTML = `<div class="no-results"><strong>专题加载失败</strong><span>${escapeHTML(error.message)}</span></div>`;
  }
}

function renderBrief(data) {
  const result = $('#brief-result');
  const statusCopy = {
    curated: ['已有专题覆盖', 'curated'],
    exploratory: ['探索性索引', 'exploratory'],
    insufficient: ['知识覆盖不足', 'insufficient'],
  }[data.status] || ['研究简报', 'exploratory'];
  const claims = (data.claims || []).map((claim) => `<article class="brief-claim ${escapeHTML(claim.position || 'qualifies')}"><span>${escapeHTML(positionLabels[claim.position] || '相关命题')}</span><strong>${escapeHTML(claim.statement)}</strong><p>${escapeHTML(claim.assessment || '')}</p></article>`).join('');
  const concepts = (data.concepts || []).map((concept) => `<button class="brief-concept" data-concept-id="${escapeHTML(concept.id)}"><span>${escapeHTML(concept.category || '未分类')}</span><strong>${escapeHTML(concept.name)}</strong></button>`).join('');
  const relations = (data.relations || []).slice(0, 6).map((relation) => `<div class="brief-relation"><strong>${escapeHTML(relation.source_name)}</strong><span>${escapeHTML(relationLabels[relation.relation_type] || relation.relation_type)}</span><strong>${escapeHTML(relation.target_name)}</strong><small>${Math.round(relation.confidence * 100)}%</small></div>`).join('');
  const sources = (data.evidence || []).slice(0, 5).map((item) => {
    const url = safeURL(item.source_url, '');
    return `<div class="brief-source"><span>证据</span><div><strong>${escapeHTML(item.concept_name)}</strong><p>${escapeHTML(item.content)}</p><small>${escapeHTML(item.source_title || '未注明来源')}${url ? ` · <a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">打开来源 ↗</a>` : ''}</small></div></div>`;
  }).join('');
  const papers = (data.papers || []).slice(0, 5).map((paper) => {
    const url = paperLink(paper);
    return `<div class="brief-paper"><span>${paper.year || '—'}</span><div><strong>${escapeHTML(paper.title)}</strong><small>${escapeHTML(paper.context_for || '')}${paper.venue ? ` · ${escapeHTML(paper.venue)}` : ''}</small></div>${url ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" aria-label="打开论文">↗</a>` : ''}</div>`;
  }).join('');
  const questions = (data.open_questions || []).map((item) => `<button class="brief-question" data-concept-id="${escapeHTML(item.concept_id)}"><span>${escapeHTML(item.concept_name)}</span>${escapeHTML(item.question)}</button>`).join('');

  result.innerHTML = `<header class="brief-header"><div><p class="eyebrow">RESEARCH BRIEF</p><h2>${escapeHTML(data.question)}</h2></div><span class="brief-status ${statusCopy[1]}">${statusCopy[0]}</span></header>
    <section class="brief-assessment"><span>当前判断</span><p>${escapeHTML(data.assessment)}</p>${data.issue ? `<button class="text-button brief-issue-link" data-issue-id="${escapeHTML(data.issue.id)}">查看完整议题：${escapeHTML(data.issue.title)} →</button>` : ''}</section>
    <div class="brief-coverage"><div><strong>${data.coverage.concepts}</strong><span>相关概念</span></div><div><strong>${data.coverage.claims}</strong><span>已有命题</span></div><div><strong>${data.coverage.relations}</strong><span>知识连接</span></div><div><strong>${data.coverage.sources}</strong><span>来源线索</span></div></div>
    ${claims ? `<section class="brief-section"><div class="section-head"><h4>关键命题</h4><span>比较观点，不直接替你下结论</span></div><div class="brief-claims">${claims}</div></section>` : ''}
    <div class="brief-columns"><section class="brief-section"><div class="section-head"><h4>概念与连接</h4><span>${data.concepts.length} 个入口</span></div><div class="brief-concepts">${concepts}</div><div class="brief-relations">${relations}</div></section>
    <section class="brief-section"><div class="section-head"><h4>来源与论文</h4><span>可追溯阅读</span></div><div class="brief-sources">${sources}${papers}</div></section></div>
    ${questions ? `<section class="brief-section"><div class="section-head"><h4>仍需回答</h4><span>来自知识档案的开放问题</span></div><div class="brief-questions">${questions}</div></section>` : ''}
    <p class="brief-limitation">${escapeHTML(data.limitation)}</p>`;

  result.querySelectorAll('[data-concept-id]').forEach((button) => button.addEventListener('click', async () => {
    switchView('explore');
    await selectConcept(button.dataset.conceptId);
  }));
  result.querySelectorAll('.brief-issue-link').forEach((button) => button.addEventListener('click', async () => {
    switchView('issues');
    await selectIssue(button.dataset.issueId);
  }));
}

async function generateBrief(event) {
  if (event) event.preventDefault();
  const question = $('#brief-input').value.trim();
  if (!question) return;
  const button = $('#brief-form').querySelector('[type="submit"]');
  button.disabled = true;
  button.textContent = '整理中…';
  $('#brief-result').innerHTML = '<div class="loading">正在匹配概念、命题与来源…</div>';
  try {
    const data = await api('/api/brief', { method: 'POST', body: JSON.stringify({ question }) });
    renderBrief(data);
  } catch (error) {
    $('#brief-result').innerHTML = `<div class="no-results"><strong>简报生成失败</strong><span>${escapeHTML(error.message)}</span></div>`;
  } finally {
    button.disabled = false;
    button.innerHTML = '生成证据简报 <span>→</span>';
  }
}

function relationTone(type) {
  if (['supports', 'is_a', 'part_of', 'depends_on'].includes(type)) return 'positive';
  if (type === 'contradicts') return 'negative';
  return 'neutral';
}

async function selectConcept(id) {
  try {
    const [concept, graphData, relationData, evidenceData] = await Promise.all([
      api(`/api/concepts/${encodeURIComponent(id)}`),
      api(`/api/graph?concept_id=${encodeURIComponent(id)}`),
      api(`/api/relations?concept_id=${encodeURIComponent(id)}`),
      api(`/api/evidence?concept_id=${encodeURIComponent(id)}`),
    ]);
    state.activeConcept = concept;
    renderConceptList(state.concepts, Number($('#concept-result-count').textContent.split(' ')[0]) || state.concepts.length);
    renderConceptDetail(concept, graphData.svg, relationData.items, evidenceData.items);
    if (window.innerWidth < 760) $('.detail-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderConceptDetail(concept, svg, relations, evidences) {
  const detail = $('#concept-detail');
  $('#empty-state').classList.add('hidden');
  detail.classList.remove('hidden');
  const color = categoryColors[concept.category] || '#5f6b76';
  const relationHTML = relations.length ? relations.map((relation) => `<div class="relation-row">
    <i class="relation-dot ${relationTone(relation.relation_type)}"></i>
    <div><strong>${escapeHTML(relation.source_name)} <span>→</span> ${escapeHTML(relation.target_name)}</strong><small>${escapeHTML(relation.evidence || '暂无关系依据')}</small></div>
    <span class="relation-name">${escapeHTML(relationLabels[relation.relation_type] || relation.relation_type)}</span>
    <b>${Math.round(relation.confidence * 100)}%</b>
  </div>`).join('') : '<div class="compact-empty">还没有关系记录</div>';
  const evidenceHTML = evidences.length ? evidences.map((item) => {
    const url = safeURL(item.source_url, '');
    return `<div class="evidence-row"><span>“</span><div><p>${escapeHTML(item.content)}</p><small>${escapeHTML(item.source_title || '未注明来源')}${url ? ` · <a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">打开来源 ↗</a>` : ''}</small></div></div>`;
  }).join('') : '<div class="compact-empty">还没有来源证据</div>';
  const sections = concept.sections || [];
  const dossierHTML = sections.length ? `<section class="detail-section dossier-section">
    <div class="section-head"><h4>知识档案</h4><span>${sections.length} 个研究切面</span></div>
    <div class="dossier-grid">${sections.map((section) => `<article class="dossier-entry ${escapeHTML(section.section_type)}">
      <p>${escapeHTML(section.title)}</p><div>${escapeHTML(section.content)}</div>
    </article>`).join('')}</div>
  </section>` : '';

  detail.innerHTML = `<header class="detail-header" style="--accent:${color}">
    <div class="big-avatar">${escapeHTML(concept.name.slice(0, 1))}</div>
    <div class="detail-title"><p>${escapeHTML(concept.category || '未分类')}</p><h3>${escapeHTML(concept.name)}</h3><span>${escapeHTML(concept.description)}</span></div>
    <button class="icon-button" id="edit-concept-btn" title="编辑概念" aria-label="编辑概念">✎</button>
  </header>
  <div class="detail-meta">${(concept.tags || []).map((tag) => `<span>${escapeHTML(tag)}</span>`).join('')}${concept.source ? `<small>来源：${escapeHTML(concept.source)}</small>` : ''}</div>
  ${dossierHTML}
  <section class="detail-section graph-section"><div class="section-head"><h4>局部关系图</h4><span>${relations.length} 条直接关系</span></div><div class="graph-canvas">${svg}</div></section>
  <section class="detail-section"><div class="section-head"><h4>关系</h4><button class="text-button" id="add-relation-btn">＋ 添加关系</button></div><div class="relation-list">${relationHTML}</div></section>
  <section class="detail-section"><div class="section-head"><h4>来源证据</h4><button class="text-button" id="add-evidence-btn">＋ 添加证据</button></div><div class="evidence-list">${evidenceHTML}</div></section>`;
  $('#edit-concept-btn').addEventListener('click', openEditConcept);
  $('#add-relation-btn').addEventListener('click', openRelationDialog);
  $('#add-evidence-btn').addEventListener('click', () => $('#evidence-dialog').showModal());
}

function openNewConcept() {
  state.editingConceptId = '';
  $('#concept-dialog-title').textContent = '添加概念';
  $('#concept-form').reset();
  $('#concept-dialog').showModal();
}

function openEditConcept() {
  const concept = state.activeConcept;
  if (!concept) return;
  state.editingConceptId = concept.id;
  $('#concept-dialog-title').textContent = '编辑概念';
  const form = $('#concept-form');
  form.elements.name.value = concept.name;
  form.elements.description.value = concept.description;
  form.elements.category.value = concept.category;
  form.elements.tags.value = (concept.tags || []).join(', ');
  form.elements.source.value = concept.source || '';
  $('#concept-dialog').showModal();
}

async function saveConcept(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  data.tags = data.tags ? data.tags.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean) : [];
  const path = state.editingConceptId ? `/api/concepts/${encodeURIComponent(state.editingConceptId)}` : '/api/concepts';
  const method = state.editingConceptId ? 'PUT' : 'POST';
  try {
    const concept = await api(path, { method, body: JSON.stringify(data) });
    form.closest('dialog').close();
    form.reset();
    state.editingConceptId = '';
    showToast(method === 'POST' ? '概念已添加' : '概念已更新');
    await Promise.all([loadStats(), loadConcepts()]);
    await selectConcept(concept.id);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openRelationDialog() {
  if (!state.activeConcept) return;
  const form = $('#relation-form');
  const [concepts, types] = await Promise.all([api('/api/concepts?limit=100'), api('/api/relations/types')]);
  const targets = concepts.items.filter((item) => item.id !== state.activeConcept.id);
  form.elements.target_id.innerHTML = targets.map((item) => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.name)} · ${escapeHTML(item.category)}</option>`).join('');
  form.elements.relation_type.innerHTML = types.types.map((type) => `<option value="${escapeHTML(type)}">${escapeHTML(relationLabels[type] || type)}</option>`).join('');
  $('#relation-source-name').textContent = state.activeConcept.name;
  form.reset();
  $('#confidence-output').value = Number(form.elements.confidence.value).toFixed(2);
  $('#relation-dialog').showModal();
}

async function saveRelation(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  data.source_id = state.activeConcept.id;
  data.confidence = Number(data.confidence);
  try {
    await api('/api/relations', { method: 'POST', body: JSON.stringify(data) });
    form.closest('dialog').close();
    showToast('关系已添加');
    await Promise.all([loadStats(), selectConcept(state.activeConcept.id)]);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function saveEvidence(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  data.concept_id = state.activeConcept.id;
  try {
    await api('/api/evidence', { method: 'POST', body: JSON.stringify(data) });
    form.closest('dialog').close();
    form.reset();
    showToast('证据已添加');
    await Promise.all([loadStats(), selectConcept(state.activeConcept.id)]);
  } catch (error) {
    showToast(error.message, true);
  }
}

function verdictCopy(status) {
  return {
    supports: ['支持', '当前存在方向一致的关系证据', '↑'],
    contradicts: ['反对', '当前存在冲突或方向相反的关系证据', '↓'],
    inconclusive: ['证据不足', '当前证据不足以形成方向性判断', '–'],
    unknown: ['未识别', '命题没有匹配到本地知识概念', '?'],
  }[status] || ['证据不足', '当前无法判断', '–'];
}

function evidenceItems(items, tone) {
  return (items || []).map((item) => `<div class="claim-evidence ${tone}"><i>${tone === 'positive' ? '+' : '−'}</i><div><strong>${escapeHTML(item.source_name || '')} ${escapeHTML(item.relation_label || relationLabels[item.relation] || item.relation)} ${escapeHTML(item.target_name || item.concept || '')}</strong><p>${escapeHTML(item.evidence || (item.match_kind === 'inferred' ? '传递关系路径' : '暂无直接来源说明'))}</p></div><span>${item.match_kind === 'inferred' ? '推断' : '直接'} · ${escapeHTML(item.level || '')}</span></div>`).join('');
}

function renderHypothesisResult(result) {
  const box = $('#hypothesis-result');
  const summary = typeof result.evidence_summary === 'string' ? JSON.parse(result.evidence_summary || '{}') : (result.evidence_summary || {});
  const claim = summary.parsed_claim || {};
  const [title, description, symbol] = verdictCopy(result.result);
  const score = Math.round((result.confidence || 0) * 100);
  const parsed = claim.subject ? `<div class="parsed-claim"><span>${escapeHTML(claim.subject.name)}</span><b>${claim.negated ? '不' : ''}${escapeHTML(claim.predicate_label || '未识别')}</b><span>${escapeHTML(claim.object?.name || '待补全')}</span></div>` : '';
  const directEvidence = `${evidenceItems(summary.supports, 'positive')}${evidenceItems(summary.contradicts, 'negative')}`;
  const papers = (summary.related_papers || []).map((paper) => `<div class="context-paper"><strong>${escapeHTML(paper.title)}</strong><span>${escapeHTML(paper.venue || '')}${paper.year ? ` · ${paper.year}` : ''}</span></div>`).join('');
  const limitations = (summary.limitations || []).map((item) => `<li>${escapeHTML(item)}</li>`).join('');
  const curatedClaims = (summary.curated_claims || []).map((item) => `<button class="curated-claim-link" data-issue-id="${escapeHTML(item.issue_id)}"><span>相关议题</span><strong>${escapeHTML(item.statement)}</strong><small>${escapeHTML(item.issue_title)} · ${Math.round(item.match_score * 100)}% 文本匹配</small></button>`).join('');
  box.className = `hypothesis-result ${result.result}`;
  box.innerHTML = `<div class="verdict-header"><span class="verdict-symbol">${symbol}</span><div><p>ANALYSIS RESULT</p><h3>${title}</h3><small>${escapeHTML(summary.rationale || description)}</small></div><div class="match-score"><strong>${score}%</strong><span>${escapeHTML(summary.score_label || '证据匹配度')}</span></div></div>
    ${parsed}
    <div class="analysis-section"><div class="section-head"><h4>用于判断的证据</h4><span>${(summary.supports || []).length + (summary.contradicts || []).length} 条</span></div>${directEvidence || '<div class="compact-empty">没有与命题方向直接匹配的关系</div>'}</div>
    ${(summary.open_questions || []).length ? `<div class="open-question">${escapeHTML(summary.open_questions[0].question)}</div>` : ''}
    ${curatedClaims ? `<div class="analysis-section"><div class="section-head"><h4>已有命题</h4><span>作为研究上下文，不参与结论计分</span></div><div class="curated-claims">${curatedClaims}</div></div>` : ''}
    ${papers ? `<div class="analysis-section"><div class="section-head"><h4>相关阅读</h4><span>不参与结论计分</span></div>${papers}</div>` : ''}
    ${limitations ? `<ul class="limitations">${limitations}</ul>` : ''}`;
  box.classList.remove('hidden');
  box.querySelectorAll('.curated-claim-link').forEach((button) => button.addEventListener('click', async () => {
    switchView('issues');
    await selectIssue(button.dataset.issueId);
  }));
}

async function submitHypothesis(event) {
  event.preventDefault();
  const input = $('#hypothesis-input');
  const button = event.target.querySelector('[type="submit"]');
  button.disabled = true;
  button.textContent = '分析中…';
  try {
    const result = await api('/api/hypothesis', { method: 'POST', body: JSON.stringify({ statement: input.value }) });
    state.lastStatement = input.value.trim();
    state.lastHypothesisId = result.id;
    renderHypothesisResult(result);
    await Promise.all([loadStats(), loadHypothesisHistory()]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = '分析命题 <span>→</span>';
  }
}

async function loadHypothesisHistory() {
  try {
    const data = await api('/api/hypotheses');
    const history = $('#hypothesis-history');
    $('#history-count').textContent = data.items.length;
    if (!data.items.length) {
      history.innerHTML = '<div class="no-results"><strong>暂无分析记录</strong><span>提交命题后会保存在本地</span></div>';
      return;
    }
    history.innerHTML = data.items.map((item) => {
      const copy = verdictCopy(item.result);
      return `<button class="history-item" data-id="${escapeHTML(item.id)}"><span class="history-status ${escapeHTML(item.result)}">${copy[2]}</span><span><strong>${escapeHTML(item.statement)}</strong><small>${copy[0]} · ${Math.round(item.confidence * 100)}% 匹配</small></span><b>›</b></button>`;
    }).join('');
    history.querySelectorAll('.history-item').forEach((button) => button.addEventListener('click', () => {
      const item = data.items.find((entry) => entry.id === button.dataset.id);
      if (!item) return;
      state.lastStatement = item.statement;
      state.lastHypothesisId = item.id;
      $('#hypothesis-input').value = item.statement;
      renderHypothesisResult(item);
    }));
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderPaths(paths) {
  const box = $('#paths-result');
  box.className = 'paths-result';
  if (!paths.length) {
    box.innerHTML = '<div class="compact-empty">当前命题不足以生成研究路径</div>';
    return;
  }
  box.innerHTML = `<div class="section-head"><h4>研究路径</h4><span>选择后记录决策</span></div><div class="path-list">${paths.map((path) => `<article class="path-card ${path.is_selected ? 'selected' : ''}"><div><strong>${escapeHTML(path.path_label)}</strong><p>${escapeHTML(path.description)}</p><span>${(path.concept_names || []).map((name) => escapeHTML(name)).join(' · ')}</span></div><button class="text-button path-select" data-path-id="${escapeHTML(path.id)}">${path.is_selected ? '已选择' : '选择'}</button></article>`).join('')}</div>`;
  box.querySelectorAll('.path-select').forEach((button) => button.addEventListener('click', async () => {
    try {
      await api('/api/paths/select', { method: 'POST', body: JSON.stringify({ path_id: button.dataset.pathId, note: '' }) });
      box.querySelectorAll('.path-card').forEach((card) => card.classList.remove('selected'));
      box.querySelectorAll('.path-select').forEach((item) => { item.textContent = '选择'; });
      button.textContent = '已选择';
      button.closest('.path-card').classList.add('selected');
      showToast('研究路径已记录');
    } catch (error) {
      showToast(error.message, true);
    }
  }));
}

async function generatePaths() {
  const statement = $('#hypothesis-input').value.trim() || state.lastStatement;
  if (!statement) {
    showToast('请先输入待验证命题', true);
    return;
  }
  const button = $('#path-btn');
  button.disabled = true;
  button.textContent = '生成中…';
  try {
    const data = await api('/api/hypothesis/paths', { method: 'POST', body: JSON.stringify({ statement, hypothesis_id: state.lastHypothesisId }) });
    state.lastHypothesisId = data.hypothesis_id;
    renderPaths(data.paths || []);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = '生成研究路径';
  }
}

function paperLink(paper) {
  if (paper.url) return safeURL(paper.url);
  if (paper.doi) return safeURL(`https://doi.org/${paper.doi}`);
  if (paper.arxiv_id) return safeURL(`https://arxiv.org/abs/${paper.arxiv_id}`);
  return '';
}

function renderPapers(data) {
  const list = $('#paper-list');
  $('#paper-result-count').textContent = `${data.total} 项结果`;
  if (!data.items.length) {
    list.innerHTML = `<div class="no-results"><strong>${state.paperMode === 'fulltext' ? '没有全文命中' : '还没有收藏论文'}</strong><span>${state.paperMode === 'fulltext' ? '尝试其他关键词' : '可从 BibTeX 或 arXiv 导入'}</span></div>`;
    return;
  }
  if (state.paperMode === 'fulltext') {
    list.className = 'fulltext-list';
    list.innerHTML = data.items.map((item) => `<article class="fulltext-hit"><div><span>${Math.round(item.score * 1000) / 10} 相关度</span><strong>${escapeHTML(item.paper_title)}</strong></div><p>${escapeHTML(item.content)}</p></article>`).join('');
    return;
  }
  list.className = 'paper-list';
  list.innerHTML = data.items.map((paper) => {
    const link = paperLink(paper);
    return `<article class="paper-card"><div class="paper-year">${paper.year || '—'}</div><div class="paper-copy"><strong>${escapeHTML(paper.title)}</strong><p>${escapeHTML((paper.authors || []).slice(0, 4).join(', '))}${(paper.authors || []).length > 4 ? ' 等' : ''}</p><small>${escapeHTML(paper.venue || '未注明来源')}${paper.doi ? ` · DOI ${escapeHTML(paper.doi)}` : ''}${paper.arxiv_id ? ` · arXiv ${escapeHTML(paper.arxiv_id)}` : ''}</small></div>${link ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener noreferrer" class="paper-link" aria-label="打开论文">↗</a>` : ''}</article>`;
  }).join('');
}

async function loadPapers() {
  if (state.paperRequest) state.paperRequest.abort();
  state.paperRequest = new AbortController();
  const query = $('#paper-search-input').value.trim();
  $('#paper-mode-description').textContent = state.paperMode === 'metadata' ? '按年份排序' : '显示命中原文片段';
  if (state.paperMode === 'fulltext' && !query) {
    renderPapers({ items: [], total: 0 });
    return;
  }
  const path = state.paperMode === 'fulltext' ? `/api/papers/fulltext?q=${encodeURIComponent(query)}` : `/api/papers${query ? `?q=${encodeURIComponent(query)}` : ''}`;
  try {
    const data = await api(path, { signal: state.paperRequest.signal });
    renderPapers(data);
  } catch (error) {
    if (error.name !== 'AbortError') showToast(error.message, true);
  }
}

async function importBibtex(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  try {
    const result = await api('/api/papers/import-bibtex', { method: 'POST', body: JSON.stringify(data) });
    form.closest('dialog').close();
    form.reset();
    showToast(`已处理 ${result.total} 篇论文`);
    await Promise.all([loadPapers(), loadStats()]);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function searchArxiv(event) {
  event.preventDefault();
  const form = event.target;
  const query = new FormData(form).get('query');
  const preview = $('#arxiv-preview');
  preview.className = 'arxiv-preview';
  preview.innerHTML = '<div class="loading">正在查询 arXiv…</div>';
  try {
    const data = await api(`/api/arxiv/search?q=${encodeURIComponent(query)}`);
    if (!data.items?.length) {
      preview.innerHTML = '<div class="no-results"><strong>没有找到论文</strong><span>网络可能暂时不可用</span></div>';
      return;
    }
    preview.innerHTML = data.items.slice(0, 8).map((item) => `<div class="arxiv-item"><div><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.arxiv_id)} · ${escapeHTML((item.authors || []).slice(0, 3).join(', '))}</small></div><button class="button secondary import-arxiv" data-id="${escapeHTML(item.arxiv_id)}">导入</button></div>`).join('');
    preview.querySelectorAll('.import-arxiv').forEach((button) => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await api('/api/arxiv/import', { method: 'POST', body: JSON.stringify({ arxiv_id: button.dataset.id }) });
        button.textContent = '已导入';
        showToast('arXiv 论文已导入');
        await Promise.all([loadPapers(), loadStats()]);
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
      }
    }));
  } catch (error) {
    preview.innerHTML = `<div class="no-results"><strong>查询失败</strong><span>${escapeHTML(error.message)}</span></div>`;
  }
}

async function openGlobalGraph() {
  const win = window.open('', '_blank', 'width=900,height=720');
  if (!win) {
    showToast('浏览器阻止了图谱窗口', true);
    return;
  }
  win.document.write('<title>Atlas · 全局知识图谱</title><body style="font-family:-apple-system,sans-serif;padding:24px">正在生成图谱…</body>');
  try {
    const data = await api('/api/graph');
    win.document.open();
    win.document.write(`<title>Atlas · 全局知识图谱</title><meta name="viewport" content="width=device-width"><body style="margin:0;padding:24px;background:#f4f6f7;color:#14202b;font-family:-apple-system,BlinkMacSystemFont,sans-serif"><h1 style="font-size:22px">Atlas 全局知识图谱</h1>${data.svg}</body>`);
    win.document.close();
  } catch (error) {
    win.close();
    showToast(error.message, true);
  }
}

async function refreshAll() {
  const button = $('#refresh-btn');
  button.disabled = true;
  try {
    await Promise.all([loadStats(), loadConcepts(), loadIssues(), loadHypothesisHistory(), loadPapers()]);
    if (state.activeConcept) await selectConcept(state.activeConcept.id);
    showToast('数据已刷新');
  } finally {
    button.disabled = false;
  }
}

function setup() {
  $('.brand').addEventListener('click', (event) => { event.preventDefault(); switchView('research'); });
  document.querySelectorAll('.view-tab').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
  const initialView = ['research', 'explore', 'issues', 'hypothesis', 'papers'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'research';
  switchView(initialView);
  $('#brief-form').addEventListener('submit', generateBrief);
  $('#brief-suggestions').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-question]');
    if (!button) return;
    $('#brief-input').value = button.dataset.question;
    generateBrief();
  });
  $('#search-input').addEventListener('input', debounce(loadConcepts));
  $('#paper-search-input').addEventListener('input', debounce(loadPapers));
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      switchView('explore');
      $('#search-input').focus();
    }
  });
  $('#category-filters').addEventListener('click', (event) => {
    const button = event.target.closest('.filter');
    if (!button) return;
    state.activeCategory = button.dataset.category;
    renderCategoryFilters();
    loadConcepts();
  });
  $('#paper-search-mode').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-mode]');
    if (!button) return;
    state.paperMode = button.dataset.mode;
    document.querySelectorAll('#paper-search-mode button').forEach((item) => {
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    loadPapers();
  });
  $('#new-concept-btn').addEventListener('click', openNewConcept);
  $('#concept-form').addEventListener('submit', saveConcept);
  $('#relation-form').addEventListener('submit', saveRelation);
  $('#relation-form').elements.confidence.addEventListener('input', (event) => { $('#confidence-output').value = Number(event.target.value).toFixed(2); });
  $('#evidence-form').addEventListener('submit', saveEvidence);
  $('#hypothesis-form').addEventListener('submit', submitHypothesis);
  $('#path-btn').addEventListener('click', generatePaths);
  $('#bibtex-btn').addEventListener('click', () => $('#bibtex-dialog').showModal());
  $('#bibtex-form').addEventListener('submit', importBibtex);
  $('#arxiv-btn').addEventListener('click', () => $('#arxiv-dialog').showModal());
  $('#arxiv-form').addEventListener('submit', searchArxiv);
  $('#open-global-graph').addEventListener('click', openGlobalGraph);
  $('#refresh-btn').addEventListener('click', refreshAll);
  Promise.all([loadStats(), loadConcepts(), loadIssues(), loadHypothesisHistory(), loadPapers(), generateBrief()]).catch((error) => showToast(error.message, true));
}

document.addEventListener('DOMContentLoaded', setup);
