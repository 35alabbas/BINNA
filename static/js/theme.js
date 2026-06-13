// Preload: run before paint to prevent flash
(function() {
  var t = localStorage.getItem('binna-theme');
  if (t === 'dark' || t === 'light') {
    document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : '');
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

// Toggle logic — call after DOM ready
function binnaThemeInit() {
  var btn = document.getElementById('binna-theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', function() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    var next = isDark ? '' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('binna-theme', next === 'dark' ? 'dark' : 'light');
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    if (!localStorage.getItem('binna-theme')) {
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : '');
    }
  });
}
document.addEventListener('DOMContentLoaded', binnaThemeInit);
