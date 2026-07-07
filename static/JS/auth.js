function switchTab(tab) {
  const loginForm = document.getElementById('login-form');
  const signupForm = document.getElementById('signup-form');
  const tabLogin = document.getElementById('tab-login');
  const tabSignup = document.getElementById('tab-signup');

  if (tab === 'login') {
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
    tabLogin.classList.add('active');
    tabSignup.classList.remove('active');
  } else {
    signupForm.classList.remove('hidden');
    loginForm.classList.add('hidden');
    tabSignup.classList.add('active');
    tabLogin.classList.remove('active');
  }
}

function showLoggedInView(name) {
  document.querySelector('.page').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');
  document.getElementById('dash-user-name').textContent = name;
}

function switchDashTab(tab) {
  document.querySelectorAll('.dash-tab').forEach(el => el.classList.add('hidden'));
  document.getElementById('tab-' + tab).classList.remove('hidden');

  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector('.nav-btn[data-tab="' + tab + '"]').classList.add('active');

  if (tab === 'tracker' && typeof loadTrackerData === 'function') {
    loadTrackerData();
  }
  if (tab === 'doubts' && typeof loadDoubtHistory === 'function') {
    loadDoubtHistory();
  }
}

function showLoggedOutView() {
  document.getElementById('dashboard').classList.add('hidden');
  document.querySelector('.page').classList.remove('hidden');
  switchTab('login');
}

window.addEventListener('DOMContentLoaded', async () => {
  const res = await fetch('/api/me');
  const data = await res.json();
  if (data.logged_in) {
    showLoggedInView(data.name);
  }
});

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  const errorEl = document.getElementById('login-error');
  errorEl.textContent = '';

  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();

  if (res.ok) {
    showLoggedInView(data.name);
  } else {
    errorEl.textContent = data.error || 'Something went wrong.';
  }
});

document.getElementById('signup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('signup-name').value;
  const email = document.getElementById('signup-email').value;
  const password = document.getElementById('signup-password').value;
  const errorEl = document.getElementById('signup-error');
  errorEl.textContent = '';

  const res = await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password })
  });
  const data = await res.json();

  if (res.ok) {
    showLoggedInView(data.name);
  } else {
    errorEl.textContent = data.error || 'Something went wrong.';
  }
});

document.getElementById('dash-logout-btn').addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  showLoggedOutView();
});