(function(global){
  'use strict';
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
    reveal();
  }
  global.BINNA_UI={init,reveal};
  document.addEventListener('DOMContentLoaded',init);
})(window);
