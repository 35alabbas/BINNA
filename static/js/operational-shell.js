(function(global){
  'use strict';
  const modules=[
    ['dc','documentControl','/legacy/dc','▤'],['dr','dailyReports','/legacy/dr','◫'],
    ['financial','contractPayment','/legacy/contract','▧'],['financial','financial','/legacy/financial','◈'],
    ['gantt','gantt','/legacy/gantt','⌁'],['subcontracts','subcontractors','/legacy/sub','◇'],
    ['submittals','drawings','/legacy/dwg','▱'],['submittals','FIR','/legacy/fir','F'],
    ['submittals','MIR','/legacy/mir','M'],['submittals','methodStatements','/legacy/ms','§'],
    ['submittals','RFI','/legacy/rfi','R'],['lbt','labTests','/legacy/lbt','⌬']
  ];
  function activePath(){return location.pathname.replace(/\/$/,'');}
  function renderNav(permissions){
    const sidebar=document.getElementById('sidebar');if(!sidebar)return;
    const extras=Array.from(sidebar.children).filter(el=>el.id==='sidebar-team-legend');
    const title='<div class="op-nav-section" data-i18n="projectNavigation">Project navigation</div>';
    const links=modules.filter(row=>!permissions||!permissions[row[0]]||permissions[row[0]].view!==false).map(row=>{
      const active=activePath()===row[2]?' active':'';
      const label=(global.BINNA_I18N&&BINNA_I18N.t(row[1]))||row[1];
      return '<a class="sidebar-item'+active+'" href="'+row[2]+'" data-module="'+row[0]+'"><span class="op-nav-icon">'+row[3]+'</span><span class="op-nav-label" data-i18n="'+row[1]+'">'+label+'</span></a>';
    }).join('');
    sidebar.innerHTML=title+links;extras.forEach(el=>sidebar.appendChild(el));
    if(global.BINNA_I18N)BINNA_I18N.localize(sidebar);
  }
  function brand(){
    const logo=document.querySelector('.topbar .logo');if(logo)logo.innerHTML='<span class="op-brand-mark">B</span><span class="op-brand-copy"><span class="op-brand-name">BINNA PM</span><span class="op-brand-domain">binnapm.com</span></span>';
    document.querySelectorAll('#binna-theme-toggle').forEach(el=>el.remove());
    const right=document.querySelector('.topbar-right');
    if(right&&!right.querySelector('.binna-language-toggle')){const button=document.createElement('button');button.type='button';button.className='binna-language-toggle';button.addEventListener('click',()=>BINNA_I18N.toggle());right.insertBefore(button,right.firstChild);}
  }
  async function init(){
    document.body.classList.add('binna-operational');brand();renderNav(null);
    const toggle=document.getElementById('sidebar-toggle-btn');if(toggle)toggle.addEventListener('click',()=>{if(global.matchMedia('(max-width: 820px)').matches)document.body.classList.toggle('op-sidebar-open');});
    const pid=global.BINNA&&BINNA.getProjectId?BINNA.getProjectId():null;
    if(pid&&BINNA.fetchProject){try{const response=await BINNA.fetchProject(pid);renderNav(response.project&&response.project.my_permissions);}catch(_){/* backend remains authoritative */}}
    if(global.BINNA_I18N)BINNA_I18N.apply();
  }
  global.BINNA_OPERATIONAL_SHELL={init,renderNav};
  document.addEventListener('DOMContentLoaded',init);
})(window);
