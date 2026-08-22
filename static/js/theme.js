/* Slice 1 is intentionally light-only. */
(function(){
  document.documentElement.setAttribute('data-theme','light');
  try{localStorage.setItem('binna-theme','light');}catch(_){}
})();
function binnaThemeInit(){document.documentElement.setAttribute('data-theme','light');}
document.addEventListener('DOMContentLoaded',binnaThemeInit);
