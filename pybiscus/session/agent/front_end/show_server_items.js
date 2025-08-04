
document.querySelectorAll('.pybiscus-server-only').forEach(el => {
  if (getComputedStyle(el).display === 'none') {
    el.style.display = 'flex';
  }
});

