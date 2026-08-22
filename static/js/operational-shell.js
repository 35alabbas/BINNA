(function(global){
  'use strict';

  const NAVIGATION=[
    {id:'workspace',labelKey:'workspace',items:[
      {id:'dashboard',labelKey:'dashboard',href:'/dashboard',icon:'⌂'},
      {id:'company',labelKey:'company',href:'/company',icon:'⌘'},
      {id:'projectDashboard',labelKey:'projectDashboard',href:'/dashboard',icon:'P',projectOnly:true},
    ]},
    {id:'project',labelKey:'projectSection',projectOnly:true,items:[
      {id:'dc',permission:'dc',labelKey:'documentControl',href:'/legacy/dc',icon:'▤',abbr:'DC'},
      {id:'dr',permission:'dr',labelKey:'dailyReports',href:'/legacy/dr',icon:'◫',abbr:'DR'},
      {id:'contract',permission:'financial',labelKey:'contractPayments',href:'/legacy/contract',icon:'▧'},
      {id:'accounts',permission:'financial',labelKey:'accounts',href:'/legacy/financial',icon:'◈'},
      {id:'gantt',permission:'gantt',labelKey:'gantt',href:'/legacy/gantt',icon:'⌁'},
      {id:'subcontracts',permission:'subcontracts',labelKey:'subcontractors',href:'/legacy/sub',icon:'◇'},
    ]},
    {id:'consultant',labelKey:'consultant',projectOnly:true,items:[
      {id:'dwg',permission:'submittals',labelKey:'drawingApprovals',href:'/legacy/dwg',icon:'▱',abbr:'DWG'},
      {id:'fir',permission:'submittals',labelKey:'fieldInspectionRequest',href:'/legacy/fir',icon:'F',abbr:'FIR'},
      {id:'mir',permission:'submittals',labelKey:'materialInspectionRequest',href:'/legacy/mir',icon:'M',abbr:'MIR'},
      {id:'ms',permission:'submittals',labelKey:'methodStatement',href:'/legacy/ms',icon:'§',abbr:'MS'},
      {id:'rfi',permission:'submittals',labelKey:'requestForInformation',href:'/legacy/rfi',icon:'R',abbr:'RFI'},
      {id:'lbt',permission:'lbt',labelKey:'laboratoryTests',href:'/legacy/lbt',icon:'⌬',abbr:'LBT'},
    ]},
  ];
  const SIDEBAR_STATE_KEY='binna-sidebar-collapsed';
  let currentPermissions=null;

  function copyItem(item,project){
    const result=Object.assign({},item);
    if(item.id==='projectDashboard'&&project&&project.id)result.href='/project/'+project.id;
    return result;
  }
  function canView(item,permissions){return !item.permission||!permissions||!permissions[item.permission]||permissions[item.permission].view!==false;}
  function readCollapsed(storage){try{return (storage||global.localStorage).getItem(SIDEBAR_STATE_KEY)==='1';}catch(_){return false;}}
  function writeCollapsed(collapsed,storage){try{(storage||global.localStorage).setItem(SIDEBAR_STATE_KEY,collapsed?'1':'0');}catch(_){}return collapsed;}
  function togglePresentation(collapsed,isArabic){return {labelKey:collapsed?'expand':'collapse',icon:isArabic?(collapsed?'⇤':'⇥'):(collapsed?'⇥':'⇤')};}
  function isMobile(){return !!(global.matchMedia&&global.matchMedia('(max-width: 820px)').matches);}
  function hasProjectContext(path,project){return !!(project&&project.id&&(/^\/project\/\d+\/?$/.test(path)||/^\/legacy\//.test(path)));}
  function visibleNavigation(permissions,hasProject,project){
    return NAVIGATION.filter(section=>!section.projectOnly||hasProject).map(section=>({id:section.id,labelKey:section.labelKey,items:section.items.filter(item=>(!item.projectOnly||hasProject)&&canView(item,permissions)).map(item=>copyItem(item,project))})).filter(section=>section.items.length);
  }
  function label(key){return global.BINNA_I18N?BINNA_I18N.t(key):key;}
  function escapeHtml(value){return String(value==null?'':value).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
  function isActive(item){const path=global.location?location.pathname.replace(/\/$/,''):'';return path===item.href||(item.id==='projectDashboard'&&path.indexOf('/project/')===0);}
  function sectionHtml(section,appStyle){
    const sectionClass=appStyle?'app-nav-section':'op-nav-section',linkClass=appStyle?'app-nav-link':'sidebar-item',iconClass=appStyle?'app-nav-icon':'op-nav-icon',labelClass=appStyle?'app-nav-label':'op-nav-label';
    return '<div class="'+sectionClass+'" data-nav-section="'+section.id+'" data-i18n="'+section.labelKey+'">'+label(section.labelKey)+'</div>'+section.items.map(item=>{const text=label(item.labelKey);return '<a class="'+linkClass+(isActive(item)?' active':'')+'" href="'+item.href+'" data-nav="'+item.id+'"'+(item.permission?' data-module="'+item.permission+'"':'')+' aria-label="'+escapeHtml(text)+'" title="'+escapeHtml(text)+'"><span class="'+iconClass+'">'+item.icon+'</span><span class="'+labelClass+'" data-i18n="'+item.labelKey+'">'+text+'</span></a>';}).join('');
  }
  function renderNav(permissions){
    currentPermissions=permissions;
    const project=global.BINNA&&BINNA.getProject?BINNA.getProject():null,path=global.location?location.pathname:'',sections=visibleNavigation(permissions,hasProjectContext(path,project),project);
    const appSidebar=document.getElementById('app-sidebar');
    if(appSidebar){const nav=appSidebar.querySelector('.app-nav');if(nav)nav.innerHTML=sections.map(section=>sectionHtml(section,true)).join('');}
    const operational=document.getElementById('sidebar');
    if(operational){const extras=Array.from(operational.children).filter(el=>!el.matches('.sidebar-section,.sidebar-item,.op-nav-body'));operational.innerHTML='<nav class="op-nav-body">'+sections.map(section=>sectionHtml(section,false)).join('')+'</nav>';extras.forEach(el=>operational.appendChild(el));}
    if(global.BINNA_I18N)BINNA_I18N.localize(document);
  }
  function updateToggleControls(collapsed){
    const presentation=togglePresentation(collapsed,!!(global.BINNA_I18N&&BINNA_I18N.isArabic)),text=label(presentation.labelKey);
    document.querySelectorAll('[data-binna-sidebar-toggle]').forEach(button=>{
      button.setAttribute('aria-expanded',String(!collapsed));button.setAttribute('aria-label',text);button.setAttribute('title',text);
      const icon=button.querySelector('[data-sidebar-toggle-icon]');if(icon)icon.textContent=presentation.icon;
      const copy=button.querySelector('[data-sidebar-toggle-label]');if(copy){copy.textContent=text;copy.setAttribute('data-i18n',presentation.labelKey);}
    });
  }
  function setCollapsed(collapsed,persist){
    document.body.classList.toggle('sidebar-collapsed',collapsed);
    document.querySelectorAll('.sidebar.collapsed').forEach(sidebar=>sidebar.classList.remove('collapsed'));
    if(isMobile()){
      document.body.classList.toggle('sidebar-open',!collapsed);
      document.body.classList.toggle('op-sidebar-open',!collapsed);
    }else{
      document.body.classList.remove('sidebar-open','op-sidebar-open');
    }
    if(persist!==false)writeCollapsed(collapsed);
    updateToggleControls(collapsed);
    return collapsed;
  }
  function toggleSidebar(){return setCollapsed(!document.body.classList.contains('sidebar-collapsed'),true);}
  function normalizeToggleControls(){
    const operational=document.getElementById('sidebar-toggle-btn');
    if(operational){operational.removeAttribute('onclick');operational.classList.add('binna-sidebar-toggle');operational.setAttribute('data-binna-sidebar-toggle','');operational.setAttribute('aria-controls','sidebar');operational.innerHTML='<span data-sidebar-toggle-icon aria-hidden="true"></span><span class="sr-only" data-sidebar-toggle-label></span>';}
    document.querySelectorAll('.app-sidebar-toggle,.app-mobile-menu').forEach(button=>button.setAttribute('data-binna-sidebar-toggle',''));
    document.querySelectorAll('[data-binna-sidebar-toggle]').forEach(button=>{if(button.dataset.binnaSidebarBound)return;button.dataset.binnaSidebarBound='1';button.addEventListener('click',toggleSidebar);});
  }
  function userMenuHtml(user){
    const username=user&&user.username?user.username:label('account'),detail=(user&&user.email)||(user&&user.company_role)||'',initial=username.charAt(0).toUpperCase();
    return '<div class="binna-user-menu"><button class="binna-user-trigger" type="button" aria-haspopup="true" aria-expanded="false"><span class="binna-user-avatar">'+escapeHtml(initial)+'</span><span class="binna-user-name">'+escapeHtml(username)+'</span><span aria-hidden="true">⌄</span></button><div class="binna-user-dropdown" hidden><div class="binna-user-label" data-i18n="accountInformation">'+label('accountInformation')+'</div><div class="binna-user-summary"><strong>'+escapeHtml(username)+'</strong>'+(detail?'<span>'+escapeHtml(detail)+'</span>':'')+'</div><div class="binna-user-label" data-i18n="languageSelection">'+label('languageSelection')+'</div><div class="binna-language-options"><button type="button" data-lang="ar">العربية</button><button type="button" data-lang="en">English</button></div><button class="binna-user-logout" type="button" data-i18n="logout">'+label('logout')+'</button></div></div>';
  }
  function renderUserMenu(){
    const right=document.querySelector('.topbar-right');if(!right)return;
    const old=right.querySelector('.binna-user-menu');if(old)old.remove();
    const user=global.BINNA&&BINNA.getUser?BINNA.getUser():null;right.insertAdjacentHTML('beforeend',userMenuHtml(user));
    right.querySelectorAll('.mgmt-language-toggle,.binna-language-toggle,.user-pill,.user-chip,.nav-logout,.btn-logout').forEach(el=>el.hidden=true);
    const menu=right.querySelector('.binna-user-menu'),trigger=menu.querySelector('.binna-user-trigger'),dropdown=menu.querySelector('.binna-user-dropdown');
    trigger.addEventListener('click',()=>{const open=dropdown.hidden;dropdown.hidden=!open;trigger.setAttribute('aria-expanded',String(open));});
    menu.querySelectorAll('[data-lang]').forEach(button=>button.addEventListener('click',()=>{if(global.BINNA_I18N)BINNA_I18N.setLang(button.dataset.lang);dropdown.hidden=true;}));
    menu.querySelector('.binna-user-logout').addEventListener('click',()=>{if(global.BINNA)BINNA.logout();});
  }
  function brand(){const logo=document.querySelector('.topbar .logo');if(logo)logo.innerHTML='<span class="op-brand-mark">B</span><span class="op-brand-copy"><span class="op-brand-name">BINNA PM</span><span class="op-brand-domain">binnapm.com</span></span>';document.querySelectorAll('#binna-theme-toggle').forEach(el=>el.remove());}
  async function init(){
    if(document.getElementById('sidebar'))document.body.classList.add('binna-operational');
    brand();renderNav(null);renderUserMenu();normalizeToggleControls();setCollapsed(readCollapsed(),false);
    const pid=global.BINNA&&BINNA.getProjectId?BINNA.getProjectId():null;
    if(pid&&BINNA.fetchProject){try{const response=await BINNA.fetchProject(pid);renderNav(response.project&&response.project.my_permissions);}catch(_){/* backend remains authoritative */}}
    if(global.BINNA&&BINNA.fetchMe){try{await BINNA.fetchMe();renderUserMenu();}catch(_){/* auth helper handles expired sessions */}}
    if(global.BINNA_I18N)BINNA_I18N.apply();
  }
  const api={navigation:NAVIGATION,stateKey:SIDEBAR_STATE_KEY,readCollapsed,writeCollapsed,togglePresentation,visibleNavigation,hasProjectContext,renderNav,renderUserMenu,userMenuHtml,setCollapsed,toggleSidebar,init};
  global.BINNA_APP_SHELL=api;global.BINNA_OPERATIONAL_SHELL=api;
  global.addEventListener('binna:languagechange',()=>{renderNav(currentPermissions);renderUserMenu();updateToggleControls(document.body.classList.contains('sidebar-collapsed'));});
  document.addEventListener('DOMContentLoaded',init);
})(window);
