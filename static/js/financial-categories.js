(function(global){
  'use strict';
  let kind='expense',data={income_categories:[],expense_categories:[]};
  const t=(en,ar)=>global.BINNA_I18N&&BINNA_I18N.isArabic?ar:en;
  function modal(){
    let el=document.getElementById('financial-category-modal');
    if(el)return el;
    el=document.createElement('div');el.id='financial-category-modal';el.className='financial-category-overlay';el.style.display='none';
    el.innerHTML='<div class="modal-box" style="width:min(560px,92vw);padding:22px"><div style="display:flex;justify-content:space-between;align-items:center"><h2 id="category-modal-title"></h2><button class="btn" type="button" data-close>×</button></div><div class="op-category-toolbar"><input id="new-category-name" maxlength="100"><button class="btn btn-primary" type="button" id="create-category"></button></div><div class="op-category-list" id="category-list"></div></div>';
    document.body.appendChild(el);el.querySelector('[data-close]').onclick=()=>el.style.display='none';
    el.querySelector('#create-category').onclick=create;
    return el;
  }
  async function open(nextKind){
    kind=nextKind;const pid=BINNA.getProjectId();if(!pid)return;
    try{data=await BINNA.fetchFinancialCategories(pid);}catch(error){BINNA.toast(BINNA.managementError(error),'error');return;}
    const el=modal();el.style.display='flex';el.style.alignItems='center';el.style.justifyContent='center';
    el.querySelector('#category-modal-title').textContent=t(kind==='income'?'Income Categories':'Expense Categories',kind==='income'?'فئات الإيرادات':'فئات المصروفات');
    el.querySelector('#new-category-name').placeholder=t('New category name','اسم الفئة الجديدة');
    el.querySelector('#create-category').textContent=t('Add Category','إضافة فئة');render();
  }
  function render(){
    const key=kind+'_categories',list=data[key]||[],host=modal().querySelector('#category-list');
    host.innerHTML=list.map(c=>'<div class="op-category-row'+(c.archived?' is-archived':'')+'"><input value="'+BINNA.esc(c.name||'')+'" data-id="'+BINNA.esc(c.id)+'"><span class="op-system-badge" style="'+(c.system_required?'':'display:none')+'">'+t('Required','مطلوب')+'</span><button class="btn" type="button" data-save="'+BINNA.esc(c.id)+'">'+t('Rename','إعادة تسمية')+'</button><button class="btn" type="button" data-archive="'+BINNA.esc(c.id)+'" '+(c.system_required?'disabled':'')+'>'+t(c.archived?'Restore':'Archive',c.archived?'استعادة':'أرشفة')+'</button></div>').join('')||'<div class="empty">'+t('No categories yet.','لا توجد فئات بعد.')+'</div>';
    host.querySelectorAll('[data-save]').forEach(b=>b.onclick=()=>save(b.dataset.save,false));
    host.querySelectorAll('[data-archive]').forEach(b=>b.onclick=()=>save(b.dataset.archive,true));
  }
  async function create(){const input=modal().querySelector('#new-category-name'),name=input.value.trim();if(!name)return;try{const r=await BINNA.createFinancialCategory(BINNA.getProjectId(),kind,name);data[kind+'_categories'].push(r.category);input.value='';render();refreshPage();}catch(e){BINNA.toast(BINNA.managementError(e),'error');}}
  async function save(id,archive){const row=modal().querySelector('[data-id="'+CSS.escape(id)+'"]');const current=(data[kind+'_categories']||[]).find(c=>String(c.id)===String(id));const payload=archive?{archived:!current.archived}:{name:row.value.trim()};try{const r=await BINNA.updateFinancialCategory(BINNA.getProjectId(),kind,id,payload);Object.assign(current,r.category);render();refreshPage();}catch(e){BINNA.toast(BINNA.managementError(e),'error');}}
  function refreshPage(){
    const source=data[kind+'_categories']||[];
    const key=kind==='income'?'incomeCategories':'expenseCategories';
    if(global.fullData)global.fullData[key]=source.map(category=>Object.assign({},category));
    if(global.data)global.data[key]=source.map(category=>Object.assign({},category));
    if(typeof global.rebuildCatFilter==='function')global.rebuildCatFilter();
    if(typeof global.applyFilter==='function')global.applyFilter();
    if(typeof global.renderPreviews==='function')global.renderPreviews();
  }
  function inject(){
    document.querySelectorAll('[data-manage-categories]').forEach(button=>{
      const buttonKind=button.dataset.manageCategories;
      button.textContent=t('Manage Categories','إدارة الفئات');
      button.onclick=()=>open(buttonKind);
    });
    document.querySelectorAll('button').forEach(button=>{
      const text=button.textContent.toLowerCase();let buttonKind=null;
      if(text.includes('add income'))buttonKind='income';if(text.includes('add expense'))buttonKind='expense';
      if(!buttonKind)return;
      if(button.parentElement.querySelector('[data-manage-categories="'+buttonKind+'"]'))return;
      const existing=button.parentElement.querySelector('[data-manage-kind="'+buttonKind+'"]');
      if(existing){existing.textContent=t('Manage Categories','إدارة الفئات');return;}
      const manage=document.createElement('button');manage.type='button';manage.className=button.className.replace('btn-primary','');manage.dataset.manageKind=buttonKind;manage.textContent=t('Manage Categories','إدارة الفئات');manage.onclick=()=>open(buttonKind);button.after(manage);
    });
  }
  document.addEventListener('DOMContentLoaded',inject);global.addEventListener('binna:languagechange',inject);
  global.BINNA_FINANCIAL_CATEGORIES={open,inject};
})(window);
