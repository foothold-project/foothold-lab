(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const notes = document.getElementById('notes');
  let current = Math.max(0, Math.min(slides.length - 1, Number(location.hash.slice(1) || 1) - 1));
  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => slide.classList.toggle('active', i === current));
    document.querySelectorAll('.note').forEach((note, i) => note.classList.toggle('active', i === current));
    history.replaceState(null, '', '#' + (current + 1));
  }
  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }
  const saved = localStorage.getItem('theme');
  if (saved) setTheme(saved);
  document.getElementById('theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  document.getElementById('notes-toggle').addEventListener('click', () => notes.classList.toggle('open'));
  addEventListener('keydown', event => {
    if (['ArrowRight', 'PageDown', ' '].includes(event.key)) show(current + 1);
    if (['ArrowLeft', 'PageUp'].includes(event.key)) show(current - 1);
    if (event.key.toLowerCase() === 'n') notes.classList.toggle('open');
    if (event.key === 'Home') show(0);
    if (event.key === 'End') show(slides.length - 1);
    if (event.key.toLowerCase() === 'f') document.documentElement.requestFullscreen?.();
  });
  show(current);
})();
