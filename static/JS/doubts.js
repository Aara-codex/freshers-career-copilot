document.getElementById('ask-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const questionInput = document.getElementById('ask-question');
  const question = questionInput.value.trim();
  const errorEl = document.getElementById('ask-error');
  const submitBtn = document.getElementById('ask-submit-btn');
  const loadingEl = document.getElementById('ask-loading');

  errorEl.textContent = '';

  if (!question) {
    errorEl.textContent = 'Please type a question.';
    return;
  }

  submitBtn.disabled = true;
  loadingEl.classList.remove('hidden');

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await res.json();

    if (!res.ok) {
      errorEl.textContent = data.error || 'Something went wrong.';
      return;
    }

    questionInput.value = '';
    await loadDoubtHistory();
  } catch (err) {
    errorEl.textContent = 'Could not reach the server.';
  } finally {
    submitBtn.disabled = false;
    loadingEl.classList.add('hidden');
  }
});

async function loadDoubtHistory() {
  try {
    const res = await fetch('/api/questions');
    const questions = await res.json();
    const container = document.getElementById('doubt-history-list');
    container.innerHTML = '';

    if (questions.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'log-empty';
      empty.textContent = 'No questions asked yet — ask your first one above.';
      container.appendChild(empty);
      return;
    }

    questions.forEach(q => {
      const item = document.createElement('div');
      item.className = 'doubt-item';
      item.innerHTML = `
        <div class="doubt-question">Q: ${escapeHtml(q.question)}</div>
        <div class="doubt-answer">${escapeHtml(q.answer)}</div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error('Could not load questions', err);
  }
}