(function(global){
  'use strict';
  const ar={
    'Bill of Quantities':'جدول الكميات','BOQ Summary':'ملخص جدول الكميات','BOQ Total':'مجموع جدول الكميات','BOQ Work Items':'فقرات جدول الكميات',
    'Variation Orders':'أوامر التغيير','VO Summary':'ملخص أوامر التغيير','VO Total':'مجموع أوامر التغيير','Net VO':'صافي أوامر التغيير','Net VO Value':'صافي قيمة أوامر التغيير',
    'Payments':'الدفعات','Final financial position':'الموقف المالي النهائي','Total advances':'إجمالي السلف','Performance guarantees':'تأمينات حسن التنفيذ','Delay penalties':'غرامات التأخير','Contract Value':'قيمة العقد','Contract Detail':'بيان العقد','Value / Notes':'القيمة / الملاحظات','Contract Notes':'ملاحظات العقد',
    'Contract End Date':'تاريخ الإنجاز التعاقدي','Contract Period':'مدة العقد','Contract Period:':'مدة العقد:','Work Item Description':'وصف فقرة العمل',
    'Work items, quantities, unit prices and totals':'فقرات العمل والكميات والأسعار والمجاميع','Quantity':'الكمية','Unit':'الوحدة','Unit Price (IQD)':'سعر الوحدة (د.ع)','Amount (IQD)':'المبلغ (د.ع)',
    'Original BOQ':'جدول الكميات الأصلي','Updated Contract':'العقد المحدّث','Updated Contract Value':'قيمة العقد المحدّثة','Contract Total (BOQ + VO)':'إجمالي العقد (جدول الكميات + أوامر التغيير)',
    'Additional or reduced work items added to the original contract':'أعمال إضافية أو مخفّضة أُدخلت على العقد الأصلي','Description':'الوصف','VO No.':'رقم أمر التغيير','VO Date':'تاريخ أمر التغيير','Extra Days':'الأيام الإضافية',
    'Total Additions (+)':'مجموع الإضافات (+)','Total Deductions (−)':'مجموع التخفيضات (−)','Total BOQ Value':'إجمالي قيمة جدول الكميات',
    '+ Add Item':'+ إضافة فقرة','+ Add Work Item':'+ إضافة فقرة عمل','+ Add VO Item':'+ إضافة أمر تغيير','+ Section Header':'+ عنوان قسم','+ Sub-Item':'+ فقرة فرعية','↑ Up':'↑ للأعلى','↓ Down':'↓ للأسفل',
    'Payment':'الدفعة','Deduction':'الاستقطاع','Total Deductions':'مجموع الاستقطاعات','Total Work Done':'إجمالي الأعمال المنجزة','Net Paid':'صافي المدفوع','Remaining Balance':'الرصيد المتبقي',
    'Total Work / Gross':'إجمالي الأعمال','Total Work Completed':'إجمالي الأعمال المنجزة','Total Net to Contractor':'صافي المستحق للمقاول','Total Received':'إجمالي المستلم',
    'Total Tax Withheld':'إجمالي الضريبة المستقطعة','Total Insurance Withheld':'إجمالي التأمينات المستقطعة','Total Penalty Withheld':'إجمالي غرامات التأخير','Total Extra Deductions':'إجمالي الاستقطاعات الإضافية',
    'Penalty Applied':'الغرامة المطبقة','Penalty Waived / Covered by VO':'الغرامة المعفاة / المغطاة بأمر تغيير','Net Penalty Outstanding':'صافي الغرامة المتبقية','Days Delayed':'أيام التأخير',
    'Private Payments Summary':'ملخص دفعات العقد الخاص','Fully user-defined payment summary — no government rules applied':'ملخص دفع يحدده المستخدم بالكامل من دون تطبيق قواعد حكومية',
    '+ Add Payment':'+ إضافة دفعة','Add work items with a fixed IQD amount — no BOQ link required. These contribute to the payment work value.':'أضف فقرات عمل بمبلغ ثابت بالدينار من دون ربط بجدول الكميات. تدخل هذه الفقرات ضمن قيمة أعمال الدفعة.',
    'Quantities, rates and completed amounts for this payment':'الكميات والأسعار والمبالغ المنجزة لهذه الدفعة','Select completed items and enter quantities for this payment':'اختر الفقرات المنجزة وأدخل كمياتها لهذه الدفعة',
    'From BOQ':'من جدول الكميات','Save Manual Items':'حفظ الفقرات اليدوية','Confirm Selected Items':'تأكيد الفقرات المختارة','✓ Done':'✓ تم','Cancel':'إلغاء',
    'Project':'المشروع','Consultant':'الاستشاري','Team':'الفريق','Financial':'المالية','Gantt Chart':'المخطط الزمني','Daily Reports':'التقارير اليومية','Document Control':'ضبط الوثائق','Drawings':'المخططات','Method Statements':'طرائق التنفيذ','Lab Tests':'الفحوصات المختبرية','Subcontractors & Suppliers':'المقاولون الثانويون والمجهزون',
    'Insurance / Guarantee':'التأمينات / الضمان','Tax Rate':'نسبة الضريبة','Daily Penalty Rate:':'نسبة الغرامة اليومية:','Insurance Required (5%):':'التأمينات المطلوبة (٥٪):','Required (5%)':'المطلوب (٥٪)','Withheld So Far':'المستقطع لغاية الآن','Still Held':'المحتجز حالياً',
    'Released — Initial Handover':'محرر — الاستلام الأولي','Released — Final Handover':'محرر — الاستلام النهائي','Remaining':'المتبقي','Original':'الأصلي','Reversed':'المعكوس','Full Reversal':'عكس كامل','Apply Reversal':'تطبيق العكس','Selected Deduction':'الاستقطاع المحدد','Remaining to reverse:':'المتبقي للعكس:',
    'By Percentage (%)':'بالنسبة المئوية (٪)','Partial Amount (IQD)':'مبلغ جزئي (د.ع)','New Cumulative Qty':'الكمية التراكمية الجديدة','Prev Cumulative':'التراكمي السابق','BOQ Total':'إجمالي جدول الكميات',
    'Draft':'مسودة','Submitted':'مقدم','Approved':'مصادق عليه','Paid':'مدفوع','Pending':'قيد الانتظار','Rejected':'مرفوض','Addition':'إضافة','Deduction':'تخفيض',
    'All contract parties, values, dates, and financial terms':'جميع أطراف العقد والقيم والتواريخ والشروط المالية','Contractor':'المقاول','Client / Employer':'صاحب العمل','Project Name':'اسم المشروع','Contract Number':'رقم العقد',
    'Currency':'العملة','Decimal Places':'المنازل العشرية','Contract Value':'قيمة العقد الأصلية','Variation Orders Total':'مجموع أوامر التغيير','Contract Total Final Value':'القيمة الإجمالية النهائية',
    'Warranty Period':'فترة الضمان','Insurance / Guarantee %':'نسبة التأمينات / الضمان','Tax Rate %':'نسبة الضريبة','Daily Penalty Rate % of contract':'نسبة الغرامة اليومية من العقد','Contract Rules / Notes':'قواعد العقد / الملاحظات',
    'days → Ends:':'يوم ← ينتهي في:','No decimals':'من دون منازل عشرية','1 decimal place':'منزلة عشرية واحدة','2 decimal places':'منزلتان عشريتان',
    'Custom…':'مخصص…','Iraqi Dinar (default)':'الدينار العراقي (الافتراضي)','US Dollar ($)':'الدولار الأمريكي ($)','Euro (€)':'اليورو (€)',
    'Print':'طباعة','Save':'حفظ','Modules':'الوحدات','Locked':'مقفل','Cannot change after payment data exists.':'لا يمكن التغيير بعد وجود بيانات دفع.',
    'Hide Dashboard':'إخفاء لوحة الملخص','Show Dashboard':'إظهار لوحة الملخص','▲ Hide Dashboard':'▲ إخفاء لوحة الملخص','▼ Show Dashboard':'▼ إظهار لوحة الملخص','Net Paid to Contractor':'صافي المدفوع للمقاول','Quick Manual Entry':'إدخال يدوي سريع','✏ Quick Manual Entry':'✏ إدخال يدوي سريع','Filter by description or item number...':'تصفية حسب الوصف أو رقم الفقرة...','Select/deselect all visible':'تحديد أو إلغاء تحديد جميع الظاهر','minimum':'الحد الأدنى','rows':'صف','Auto from BOQ total':'تلقائي من مجموع جدول الكميات','Auto from VO section':'تلقائي من قسم أوامر التغيير','Auto = Contract Value + VO':'تلقائي = قيمة العقد + أوامر التغيير','Choose File':'اختيار ملف','No file chosen':'لم يتم اختيار ملف','.xlsx / .csv · 5 MB · 5,000 rows':'‎.xlsx / .csv · ٥ ميغابايت · ٥٬٠٠٠ صف','Reverse a Previous Deduction':'عكس استقطاع سابق','↩ Reverse a Previous Deduction':'↩ عكس استقطاع سابق',
    'IQD — Iraqi Dinar (default)':'IQD — الدينار العراقي (الافتراضي)','USD — US Dollar ($)':'USD — الدولار الأمريكي ($)','EUR — Euro (€)':'EUR — اليورو (€)','0 — No decimals (1,500)':'٠ — من دون منازل عشرية (١٬٥٠٠)','1 decimal place (1,500.0)':'منزلة عشرية واحدة (١٬٥٠٠٫٠)','2 decimal places (1,500.00)':'منزلتان عشريتان (١٬٥٠٠٫٠٠)',
    'No BOQ items.':'لا توجد فقرات في جدول الكميات.','No payments received yet':'لم تُستلم دفعات بعد','No stoppages added yet.':'لا توجد توقفات مسجلة.','Nothing to undo':'لا يوجد إجراء للتراجع',
    'Work item description':'وصف فقرة العمل','Sub-item description':'وصف الفقرة الفرعية','Section / Work Category Title':'عنوان القسم / فئة العمل','Payment description':'وصف الدفعة','Reason / reference':'السبب / المرجع','Company name':'اسم الشركة','Client name':'اسم صاحب العمل','Project name':'اسم المشروع','Contract reference no.':'رقم مرجع العقد','Any special contract rules...':'أي قواعد خاصة بالعقد...'
  };
  const reverse={};Object.keys(ar).forEach(key=>{reverse[ar[key]]=key;});
  const sourceNodes=new WeakMap(),sourceAttrs=new WeakMap();
  function hasArabic(value){return /[\u0600-\u06ff]/.test(value||'');}
  function bilingual(value,arabic){
    const clean=String(value||'').trim();
    for(const sep of [' / ',' — ',' | ']){if(clean.includes(sep)){const parts=clean.split(sep);const arPart=parts.find(hasArabic),enPart=parts.find(part=>/[A-Za-z]/.test(part));if(arabic&&arPart)return arPart.trim();if(!arabic&&enPart)return enPart.trim();}}
    return null;
  }
  function translated(value,arabic){
    const trimmed=String(value||'').trim();if(!trimmed)return value;
    const bi=bilingual(trimmed,arabic);if(bi)return bi;
    if(arabic){if(ar[trimmed])return ar[trimmed];return BINNA_I18N.toArabicDigits(trimmed);}
    if(reverse[trimmed])return reverse[trimmed];return BINNA_I18N.normalizeDigits(trimmed).replace(/,/g,',');
  }
  function localizeTextNode(node){
    if(!sourceNodes.has(node))sourceNodes.set(node,node.nodeValue);const source=sourceNodes.get(node),spaceStart=(source.match(/^\s*/)||[''])[0],spaceEnd=(source.match(/\s*$/)||[''])[0];node.nodeValue=spaceStart+translated(source.trim(),BINNA_I18N.isArabic)+spaceEnd;
  }
  function localizeAttr(el,attr){
    let record=sourceAttrs.get(el);if(!record){record={};sourceAttrs.set(el,record);}if(!(attr in record))record[attr]=el.getAttribute(attr)||'';if(record[attr])el.setAttribute(attr,translated(record[attr],BINNA_I18N.isArabic));
  }
  function localizeTree(root){
    const scope=root&&root.nodeType?root:document.body;if(!scope)return;
    const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT,{acceptNode(node){const parent=node.parentElement;if(!parent||/^(SCRIPT|STYLE|TEXTAREA)$/.test(parent.tagName)||parent.closest('#proj-name,#proj-code,#boq-body,#vo-body input,#pay-rows-container input'))return NodeFilter.FILTER_REJECT;return node.nodeValue.trim()?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;}});const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);nodes.forEach(localizeTextNode);
    const elements=scope.querySelectorAll?scope.querySelectorAll('input[placeholder],textarea[placeholder],[title],option,input.cell-in.label[readonly]'):[];elements.forEach(el=>{if(el.hasAttribute('placeholder'))localizeAttr(el,'placeholder');if(el.hasAttribute('title'))localizeAttr(el,'title');if(el.matches('input.cell-in.label[readonly]')){let record=sourceAttrs.get(el);if(!record){record={};sourceAttrs.set(el,record);}if(!('value' in record))record.value=el.value;el.value=translated(record.value,BINNA_I18N.isArabic);}});
  }
  function localizeNumericInputs(){document.querySelectorAll('input[inputmode="decimal"],#cd-tax,#cd-insurance,#cd-penalty-rate').forEach(input=>{if(!input.value)return;const normalized=BINNA_I18N.normalizeDigits(input.value).replace(/٬/g,'').replace(/,/g,'');input.value=BINNA_I18N.isArabic?BINNA_I18N.toArabicDigits(normalized).replace('.', '٫'):normalized.replace('٫','.');});}
  function refresh(){if(global._contractReady&&typeof global.collectAll==='function')global.collectAll();localizeTree(document.body);if(global._contractReady){if(typeof global.renderContractStoppages==='function')global.renderContractStoppages();if(typeof global.renderContractExtensions==='function')global.renderContractExtensions();if(typeof global.updateSummaries==='function')global.updateSummaries();}localizeNumericInputs();}
  global.BINNA_CONTRACT_I18N={refresh,localizeTree};
  global.addEventListener('binna:languagechange',refresh);
  document.addEventListener('DOMContentLoaded',()=>{refresh();const observer=new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{if(node.nodeType===1){localizeTree(node);BINNA_I18N.localize(node);}})));observer.observe(document.body,{childList:true,subtree:true});});
})(window);
