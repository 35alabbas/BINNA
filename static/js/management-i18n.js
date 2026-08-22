(function(global){
  'use strict';
  const messages={
    en:{language:'العربية',dashboard:'Dashboard',company:'Company',project:'Project',projectsManager:'Projects manager',projectManager:'Project manager',employees:'Project employees',permissions:'Module permissions',lifecycle:'Project lifecycle',closeProject:'Close project',reopenProject:'Reopen project',monitoring:'Monitoring comments',audit:'Audit timeline',addComment:'Add comment',save:'Save',current:'Current',notAssigned:'Not assigned',closed:'Closed',active:'Open',view:'View',edit:'Edit',migration1:'Management roles are unavailable until the Phase 1B-1 database update is applied.',migration2:'Lifecycle, monitoring comments, and audit records are unavailable until the Phase 1B-2 database update is applied.',interim:'If no project manager is selected, the company projects manager will serve as interim project manager.'},
    ar:{language:'English',dashboard:'لوحة المشاريع',company:'الشركة',project:'المشروع',projectsManager:'مدير المشاريع',projectManager:'مدير المشروع',employees:'موظفو المشروع',permissions:'صلاحيات الوحدات',lifecycle:'دورة حياة المشروع',closeProject:'إغلاق المشروع',reopenProject:'إعادة فتح المشروع',monitoring:'تعليقات المتابعة',audit:'سجل التدقيق',addComment:'إضافة تعليق',save:'حفظ',current:'الحالي',notAssigned:'غير معيّن',closed:'مغلق',active:'مفتوح',view:'عرض',edit:'تعديل',migration1:'أدوار الإدارة غير متاحة حتى يتم تطبيق تحديث قاعدة بيانات المرحلة 1B-1.',migration2:'إغلاق المشاريع وتعليقات المتابعة وسجل التدقيق غير متاحة حتى يتم تطبيق تحديث قاعدة بيانات المرحلة 1B-2.',interim:'إذا لم يتم اختيار مدير للمشروع، فسيتولى مدير المشاريع إدارة المشروع مؤقتاً.'}
  };
  const api={
    get lang(){return localStorage.getItem('binna_language')==='ar'?'ar':'en';},
    t(key){return (messages[this.lang]||messages.en)[key]||messages.en[key]||key;},
    apply(){
      const lang=this.lang,root=document.documentElement;root.lang=lang;root.dir=lang==='ar'?'rtl':'ltr';
      document.querySelectorAll('[data-i18n]').forEach(el=>{const v=(messages[lang]||{})[el.dataset.i18n];if(v)el.textContent=v;});
      document.querySelectorAll('.mgmt-language-toggle').forEach(el=>el.textContent=this.t('language'));
      global.dispatchEvent(new CustomEvent('binna:languagechange',{detail:{lang}}));
    },
    toggle(){localStorage.setItem('binna_language',this.lang==='en'?'ar':'en');this.apply();}
  };
  global.BINNA_I18N=api;
  document.addEventListener('DOMContentLoaded',()=>api.apply());
})(window);
