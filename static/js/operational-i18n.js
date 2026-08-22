(function(global){
  'use strict';
  const phrases={
    'Document Control':'ضبط الوثائق','Daily Reports':'التقارير اليومية',
    'Contract & Payment':'العقد والدفعات','Financial':'المالية','Income':'الإيرادات',
    'Expenses':'المصروفات','Gantt Chart':'المخطط الزمني',
    'Subcontractors & Suppliers':'المقاولون الثانويون والمجهزون',
    'Drawings':'المخططات','Field Inspection Requests':'طلبات الفحص الموقعي',
    'Material Inspection Requests':'طلبات فحص المواد','Method Statements':'طرائق التنفيذ',
    'Requests for Information':'طلبات المعلومات','Lab Tests':'الفحوصات المختبرية',
    'Dashboard':'لوحة المشاريع','Project':'المشروع','Project Navigation':'تنقل المشروع',
    'Save':'حفظ','Save Changes':'حفظ التغييرات','Saved':'تم الحفظ','Cancel':'إلغاء',
    'Close':'إغلاق','Delete':'حذف','Edit':'تعديل','Add':'إضافة','Update':'تحديث',
    'Search':'بحث','Filter':'تصفية','Print':'طباعة','Export':'تصدير','Import':'استيراد',
    'Status':'الحالة','Date':'التاريخ','Description':'الوصف','Reference':'المرجع',
    'Amount':'المبلغ','Currency':'العملة','Exchange Rate':'سعر الصرف',
    'Notes':'الملاحظات','Actions':'الإجراءات','Category':'الفئة','Categories':'الفئات',
    'Manage Categories':'إدارة الفئات','Add Income Entry':'إضافة قيد إيراد',
    'Add Expense Entry':'إضافة قيد مصروف','Income Categories':'فئات الإيرادات',
    'Expense Categories':'فئات المصروفات','Archive':'أرشفة','Archived':'مؤرشف',
    'Rename':'إعادة تسمية','Active':'نشط','Closed':'مغلق','Paid':'مدفوع',
    'Unpaid':'غير مدفوع','Draft':'مسودة','Approved':'مصادق عليه','Certified':'مصدق',
    'Total':'الإجمالي','Balance':'الرصيد','Contract Value':'قيمة العقد',
    'Total Paid':'إجمالي المدفوع','Add Payment':'إضافة دفعة','Payments':'الدفعات',
    'No records found.':'لا توجد سجلات.','No entries yet.':'لا توجد قيود بعد.',
    'Loading…':'جارٍ التحميل…','Loading...':'جارٍ التحميل…',
    'Required':'مطلوب','Yes':'نعم','No':'لا','Name':'الاسم','Type':'النوع',
    'Client':'صاحب العمل','Consultant':'الاستشاري','Contractor':'المقاول',
    'Supplier':'المجهز','Subcontractor':'المقاول الثانوي','Employees':'الموظفون',
    'View':'عرض','Permission':'الصلاحية','Permissions':'الصلاحيات',
    'From':'من','To':'إلى','Start Date':'تاريخ البدء','End Date':'تاريخ الانتهاء',
    'Duration':'المدة','Progress':'التقدم','Schedule Progress':'التقدم الزمني',
    'Financial Progress':'التقدم المالي','Project Dashboard':'لوحة المشروع',
    'Back':'رجوع','Log out':'تسجيل الخروج','Add Row':'إضافة صف',
    'Add Item':'إضافة فقرة','Upload':'رفع','Download':'تنزيل','Open':'فتح',
    'Not recorded':'غير مسجل','System generated':'منشأ تلقائياً',
    'Linked payment expense':'مصروف مرتبط بدفعة','Reversal':'قيد عكسي',
    'Modules':'الوحدات','Hide Dashboard':'إخفاء الملخص','Show Dashboard':'عرض الملخص',
    'Total Income':'إجمالي الإيرادات','Total Expenses':'إجمالي المصروفات',
    'Net Balance':'صافي الرصيد','Income & Expenses':'الإيرادات والمصروفات',
    'Track all cash in and out — IQD main currency, USD supported with exchange rate':'تتبّع جميع التدفقات النقدية الداخلة والخارجة — الدينار العراقي هو العملة الأساسية مع دعم الدولار وسعر الصرف',
    'USD Exchange Rate:':'سعر صرف الدولار:','IQD per 1 USD':'دينار عراقي لكل دولار واحد',
    'View All Income →':'عرض جميع الإيرادات ←','View All Expenses →':'عرض جميع المصروفات ←',
    'Description / Source':'الوصف / المصدر','Description / Expense':'الوصف / المصروف',
    'Cur.':'العملة','Amount (IQD)':'المبلغ (د.ع)','Rate':'السعر',
    '— No Category —':'— بدون فئة —','All Categories':'جميع الفئات',
    '+ Add Income Entry':'+ إضافة قيد إيراد','+ Add Expense Entry':'+ إضافة قيد مصروف',
    'Uncategorised':'غير مصنف','No data':'لا توجد بيانات','Show All':'عرض الكل',
    'Paginate':'تقسيم الصفحات','Prev':'السابق','Next':'التالي',
    'Payment Log':'سجل الدفعات','Log Payment':'تسجيل دفعة','Invoice Ref':'مرجع الفاتورة',
    'PO Value':'قيمة أمر الشراء','Balance Payable':'الرصيد المستحق',
    'Prepared by (name)':'أعدّه (الاسم)','Title':'الصفة','Signed copy':'نسخة موقعة',
    'Payment system locked after payment data':'تم تثبيت نظام الدفع بعد إدخال بيانات الدفعات',
    'Marked paid':'تم التأشير كمدفوع','Exchange rate is required before marking paid':'سعر الصرف مطلوب قبل التأشير كمدفوع',
    'Committed':'الملتزم به','Retained':'الاستقطاع','Balance Payable':'الرصيد المستحق',
    'Subcontracts':'المقاولات الثانوية','Supply Agreements':'اتفاقيات التجهيز',
    'Subcontracts & Supply Agreements':'المقاولات الثانوية واتفاقيات التجهيز',
    'Party':'الطرف','Kind':'النوع','Cert':'الشهادة','Monthly':'شهري',
    'Incoming':'وارد','Outgoing':'صادر','Subject':'الموضوع','Sender':'المرسل',
    'Recipient':'المستلم','Letter':'الكتاب','Letters':'الكتب','Revision':'المراجعة',
    'Discipline':'الاختصاص','Location':'الموقع','Result':'النتيجة','Weather':'الطقس',
    'Manpower':'القوى العاملة','Visitors':'الزوار','Work Done':'الأعمال المنجزة',
    'Attachments':'المرفقات','Attachment':'المرفق','Code':'الرمز','Created':'تاريخ الإنشاء',
    'Pending':'قيد الانتظار','Rejected':'مرفوض','Submitted':'مقدم','Returned':'معاد',
    'Approved as noted':'مصادق عليه مع ملاحظات','New Record':'سجل جديد',
    'New Letter':'كتاب جديد','New Daily Report':'تقرير يومي جديد','Summary':'الملخص',
    'Activity':'الفعالية','Predecessor':'السابق','Stoppage':'التوقف','Stoppages':'التوقفات',
    'Baseline':'خط الأساس','Critical':'حرج','Delay':'تأخير','Milestone':'علامة مرحلية',
    'Contractual Completion':'الإنجاز التعاقدي','Actual Completion':'الإنجاز الفعلي'
  };
  const lowerPhrases=Object.fromEntries(Object.entries(phrases).map(([key,value])=>[key.toLowerCase(),value]));
  const originals=new WeakMap();
  const attrOriginals=new WeakMap();
  const protectedSelector='input,textarea,option,[contenteditable],.user-content,.project-name,.party-name,.description-cell';
  function translateText(node,arabic){
    if(!node.parentElement||node.parentElement.closest(protectedSelector))return;
    const raw=originals.has(node)?originals.get(node):node.nodeValue;
    if(!originals.has(node))originals.set(node,raw);
    const leading=(raw.match(/^\s*/)||[''])[0],trailing=(raw.match(/\s*$/)||[''])[0];
    const core=raw.trim();
    if(!core)return;
    let translated=arabic?(phrases[core]||lowerPhrases[core.toLowerCase()]||core):core;
    if(arabic&&translated===core){
      translated=translated
        .replace(/^Total Income:/i,'إجمالي الإيرادات:')
        .replace(/^Total Expenses:/i,'إجمالي المصروفات:')
        .replace(/^Total Paid:/i,'إجمالي المدفوع:')
        .replace(/^Balance:/i,'الرصيد:')
        .replace(/^Payment\s+(\d+)/i,'دفعة $1')
        .replace(/^(\d+) total$/i,'$1 إجمالي')
        .replace(/^No entries yet/i,'لا توجد قيود بعد')
        .replace(/^No records/i,'لا توجد سجلات');
    }
    if(arabic&&node.parentElement.matches('.row-num,.num,.mono,.mono-in,.metric,.stat,.pagination button,[data-localized-number]'))translated=BINNA_I18N.toArabicDigits(translated);
    if(arabic&&/^[+−-]?[\d\s.,٬٫%]+(?:\s*(?:IQD|USD|EUR|days?))?$/.test(core))translated=BINNA_I18N.toArabicDigits(translated);
    node.nodeValue=leading+translated+trailing;
  }
  function translateAttrs(el,arabic){
    if(!attrOriginals.has(el))attrOriginals.set(el,{});
    const saved=attrOriginals.get(el);
    ['placeholder','title','aria-label'].forEach(attr=>{
      if(el.hasAttribute(attr)&&saved[attr]===undefined)saved[attr]=el.getAttribute(attr);
      if(saved[attr]!==undefined)el.setAttribute(attr,arabic&&phrases[saved[attr]]?phrases[saved[attr]]:saved[attr]);
    });
  }
  function localize(root){
    if(!global.BINNA_I18N)return;
    const arabic=BINNA_I18N.isArabic;
    const walker=document.createTreeWalker(root||document.body,NodeFilter.SHOW_TEXT);
    let node;while((node=walker.nextNode()))translateText(node,arabic);
    (root||document).querySelectorAll('[placeholder],[title],[aria-label]').forEach(el=>translateAttrs(el,arabic));
    document.querySelectorAll('[data-binna-number]').forEach(el=>{
      const value=el.getAttribute('data-binna-number');
      el.textContent=BINNA_I18N.formatNumber(value);
    });
  }
  let queued=false;
  function queue(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;localize(document.body);});}
  document.addEventListener('DOMContentLoaded',()=>{
    localize(document.body);
    new MutationObserver(queue).observe(document.body,{childList:true,subtree:true});
  });
  global.addEventListener('binna:languagechange',()=>localize(document.body));
  global.BINNA_OPERATIONAL_I18N={localize,phrases};
})(window);
