document.getElementById('analyze-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const target = document.getElementById('target-name-input').value.trim();
  const targetType = document.getElementById('target-type-select').value;
  const resumeText = document.getElementById('resume-text').value.trim();
  const errorEl = document.getElementById('analyze-error');
  const submitBtn = document.getElementById('analyze-submit-btn');
  const loadingEl = document.getElementById('analyze-loading');
  const resultsEl = document.getElementById('analyze-results');

  errorEl.textContent = '';
  resultsEl.classList.add('hidden');

  if (!target || !resumeText) {
    errorEl.textContent = 'Please enter a target name and paste your resume/GitHub summary.';
    return;
  }

  submitBtn.disabled = true;
  loadingEl.classList.remove('hidden');

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_name: target, target_type: targetType, resume_text: resumeText })
    });
    const data = await res.json();

    if (!res.ok) {
      errorEl.textContent = data.error || 'Something went wrong. Please try again.';
      return;
    }

    renderResults(data);
  } catch (err) {
    errorEl.textContent = 'Could not reach the server. Is it still running?';
  } finally {
    submitBtn.disabled = false;
    loadingEl.classList.add('hidden');
  }
});

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatBold(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function renderResults(data) {
  document.getElementById('score-number').textContent = data.overall_readiness_score ?? '—';

  const badge = document.getElementById('data-source-badge');
  if (data.data_source === 'curated') {
    badge.textContent = '✓ Based on curated real interview data';
    badge.className = 'data-source-badge curated';
  } else {
    badge.textContent = 'ℹ Based on AI general knowledge (no curated data for this target yet)';
    badge.className = 'data-source-badge general';
  }

  const strengthsList = document.getElementById('strengths-list');
  strengthsList.innerHTML = '';
  (data.strengths || []).forEach(item => {
    const li = document.createElement('li');
    li.innerHTML = formatBold(item);
    strengthsList.appendChild(li);
  });

  const gapsList = document.getElementById('gaps-list');
  gapsList.innerHTML = '';
  (data.gaps || []).forEach(item => {
    const li = document.createElement('li');
    li.innerHTML = formatBold(item);
    gapsList.appendChild(li);
  });

  const fixList = document.getElementById('fix-list');
  fixList.innerHTML = '';
  (data.prioritized_fix_list || []).forEach(item => {
    const li = document.createElement('li');
    li.innerHTML = formatBold(item);
    fixList.appendChild(li);
  });

  document.getElementById('analyze-results').classList.remove('hidden');
}