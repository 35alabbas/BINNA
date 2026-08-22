(function(global){
  'use strict';
  const KEY='binna-sidebar-collapsed';
  function isMobile(){return global.matchMedia('(max-width: 820px)').matches;}
  function setExpanded(expanded){
    if(isMobile()) document.body.classList.toggle('sidebar-open',expanded);
    else {
      document.body.classList.toggle('sidebar-collapsed',!expanded);
      try{localStorage.setItem(KEY,expanded?'0':'1');}catch(_){}
    }
    document.querySelectorAll('.app-sidebar-toggle').forEach(btn=>btn.setAttribute('aria-expanded',String(expanded)));
  }
  function toggleSidebar(){
    const expanded=isMobile()?document.body.classList.contains('sidebar-open'):!document.body.classList.contains('sidebar-collapsed');
    setExpanded(!expanded);
  }
  function reveal(){
    const reduce=global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.querySelectorAll('[data-reveal]').forEach((el,i)=>{
      el.classList.add('ui-reveal');el.style.setProperty('--reveal-delay',reduce?'0ms':`${Math.min(i,8)*40}ms`);
      requestAnimationFrame(()=>el.classList.add('is-visible'));
    });
    document.querySelectorAll('[data-progress]').forEach(el=>{
      const value=Math.max(0,Math.min(100,Number(el.dataset.progress)||0));
      requestAnimationFrame(()=>{el.style.width=`${value}%`;});
    });
  }
  function init(){
    if(!isMobile()){
      try{document.body.classList.toggle('sidebar-collapsed',localStorage.getItem(KEY)==='1');}catch(_){}
    }
    document.querySelectorAll('.app-sidebar-toggle,.app-mobile-menu').forEach(btn=>btn.addEventListener('click',toggleSidebar));
    document.querySelectorAll('.app-nav-link').forEach(link=>link.addEventListener('click',()=>{if(isMobile())setExpanded(false);}));
    reveal();
  }
  global.BINNA_UI={init,toggleSidebar,reveal,setExpanded};
  document.addEventListener('DOMContentLoaded',init);
})(window);
