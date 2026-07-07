async function loadTrackerData() {
  await loadGuidance();

  // Load gaps for the dropdown
  try {
    const gapsRes = await fetch('/api/gaps');
    const gaps = await gapsRes.json();
    const select = document.getElementById('log-gap-select');

    // Keep the first "General practice" option, remove the rest, then rebuild
    select.innerHTML = '<option value="">General practice (not tied to a specific gap)</option>';
    gaps
      .filter(g => g.status !== 'closed')
      .forEach(g => {
        const opt = document.createElement('option');
        opt.value = g.id;
        opt.textContent = `[${g.target_name}] ${g.gap_description}`;
        select.appendChild(opt);
      });
  } catch (err) {
    console.error('Could not load gaps', err);
  }

  // Load streaks + history
  try {
    const logsRes = await fetch('/api/logs');
    const data = await logsRes.json();

    document.getElementById('current-streak').textContent = data.current_streak;
    document.getElementById('longest-streak').textContent = data.longest_streak;

    const historyList = document.getElementById('log-history-list');
    historyList.innerHTML = '';

    if (data.logs.length === 0) {
      const li = document.createElement('li');
      li.textContent = 'No activity logged yet — log your first practice above.';
      li.className = 'log-empty';
      historyList.appendChild(li);
    } else {
      data.logs.forEach(log => {
        const li = document.createElement('li');
        li.className = 'log-entry';
        const gapTag = log.gap_description ? `<span class="log-gap-tag">${log.gap_description}</span>` : '';
        li.innerHTML = `
          <div class="log-entry-top">
            <span class="log-date">${log.log_date}</span>
            ${log.minutes_spent ? `<span class="log-minutes">${log.minutes_spent} min</span>` : ''}
          </div>
          <div class="log-activity-text">${log.activity}</div>
          ${gapTag}
        `;
        historyList.appendChild(li);
      });
    }
  } catch (err) {
    console.error('Could not load logs', err);
  }
}

document.getElementById('log-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const gapId = document.getElementById('log-gap-select').value;
  const activity = document.getElementById('log-activity').value.trim();
  const minutes = document.getElementById('log-minutes').value;
  const errorEl = document.getElementById('log-error');
  const submitBtn = document.getElementById('log-submit-btn');

  errorEl.textContent = '';

  if (!activity) {
    errorEl.textContent = 'Please describe what you practiced.';
    return;
  }

  const streakBefore = parseInt(document.getElementById('current-streak').textContent, 10) || 0;
  const longestBefore = parseInt(document.getElementById('longest-streak').textContent, 10) || 0;

  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gap_id: gapId || null,
        activity: activity,
        minutes_spent: minutes ? parseInt(minutes, 10) : null
      })
    });
    const data = await res.json();

    if (!res.ok) {
      errorEl.textContent = data.error || 'Something went wrong.';
      return;
    }

    document.getElementById('log-activity').value = '';
    document.getElementById('log-minutes').value = '';
    document.getElementById('log-gap-select').value = '';

    await loadTrackerData();

    if (data.current_streak > longestBefore) {
      showCelebration('record');
    } else if (data.current_streak > streakBefore) {
      showCelebration('streak');
    }
    if (gapId) {
      showCelebration('improving');
    }
  } catch (err) {
    errorEl.textContent = 'Could not reach the server.';
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById('refresh-guidance-btn').addEventListener('click', loadGuidance);

async function loadGuidance() {
  const guidanceText = document.getElementById('guidance-text');
  const refreshBtn = document.getElementById('refresh-guidance-btn');
  refreshBtn.disabled = true;
  guidanceText.textContent = 'Thinking about your next steps…';

  try {
    const res = await fetch('/api/guidance');
    const data = await res.json();
    if (res.ok) {
      guidanceText.textContent = data.guidance;
    } else {
      guidanceText.textContent = data.error || 'Could not load guidance right now.';
    }
  } catch (err) {
    guidanceText.textContent = 'Could not reach the server.';
  } finally {
    refreshBtn.disabled = false;
  }
}