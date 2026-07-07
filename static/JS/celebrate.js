// ---------- CELEBRATION SYSTEM ----------
// Shows a small animated toast with confetti for milestone moments.

const CELEBRATION_CONFIG = {
  streak: { icon: '🔥', message: 'Streak going strong!', color: '#C89B3C' },
  record: { icon: '🏆', message: 'New longest streak!', color: '#C89B3C' },
  improving: { icon: '💪', message: 'Gap marked as improving!', color: '#2FA89A' },
  closed: { icon: '🎉', message: 'Gap closed — great work!', color: '#7C6FE0' },
};

function showCelebration(type) {
  const config = CELEBRATION_CONFIG[type];
  if (!config) return;

  const toast = document.createElement('div');
  toast.className = 'celebration-toast';
  toast.style.setProperty('--celebrate-color', config.color);

  toast.innerHTML = `
    <div class="celebration-icon">${config.icon}</div>
    <div class="celebration-message">${config.message}</div>
  `;

  // Confetti pieces
  const confettiColors = ['#C89B3C', '#2FA89A', '#7C6FE0', '#C1442E'];
  for (let i = 0; i < 14; i++) {
    const piece = document.createElement('span');
    piece.className = 'confetti-piece';
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.background = confettiColors[i % confettiColors.length];
    piece.style.animationDelay = `${Math.random() * 0.3}s`;
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    toast.appendChild(piece);
  }

  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('celebration-show'));

  setTimeout(() => {
    toast.classList.remove('celebration-show');
    setTimeout(() => toast.remove(), 400);
  }, 2800);
}