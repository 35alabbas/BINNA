(function(global){
  'use strict';
  const phrases={
    'Document Control':'ضبط الوثائق','Daily Reports':'التقارير اليومية',
    'Contract & Payment':'العقد والسلف','Contract & Payments':'العقد والسلف','Financial':'المالية','Income':'الإيرادات',
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
    'Uncategorised':'غير مصنف','No data':'لا توجد بيانات','Show All':'عرض الكل','Paginate':'عرض الصفحات','Prev':'السابق','Next':'التالي','▲ Up':'▲ للأعلى',
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
    'Contractual Completion':'الإنجاز التعاقدي','Actual Completion':'الإنجاز الفعلي',
    'Project portfolio':'محفظة المشاريع','Total Projects':'إجمالي المشاريع','All Statuses':'جميع الحالات',
    'All lifecycle states':'جميع حالات دورة المشروع','On Hold':'متوقف مؤقتاً','Completed':'مكتمل',
    'New Project':'مشروع جديد','Create Project':'إنشاء المشروع','Edit Project':'تعديل المشروع',
    'Fill in the project details below':'أدخل تفاصيل المشروع أدناه','Project Code':'رمز المشروع',
    'Project Name':'اسم المشروع','Client / Employer':'صاحب العمل','Short code used in all document references':'رمز مختصر يستخدم في جميع مراجع المستندات',
    'Short project summary (optional)':'ملخص قصير للمشروع (اختياري)','Project manager (optional)':'مدير المشروع (اختياري)','Project Manager (optional)':'مدير المشروع (اختياري)',
    'EMPLOYEE':'الموظف','PROJECT ROLE':'دور المشروع','ASSIGNMENT':'التعيين',
    'Use projects manager as interim manager':'استخدام مدير المشاريع مديراً مؤقتاً',
    'Project manager':'مدير المشروع','Project lifecycle':'دورة المشروع','Close project':'إغلاق المشروع','Reopen project':'إعادة فتح المشروع',
    'Project employees':'موظفو المشروع','Add project employee':'إضافة موظف إلى المشروع','Add employee':'إضافة موظف',
    'Company account email or username':'البريد الإلكتروني أو اسم مستخدم حساب الشركة','Project role':'دور المشروع',
    'Viewer':'مشاهد','Member':'عضو','Admin':'مسؤول','Module permissions':'صلاحيات الوحدات',
    'Monitoring comments':'ملاحظات المتابعة','Audit timeline':'سجل التدقيق','Add comment':'إضافة ملاحظة',
    'No monitoring comments yet.':'لا توجد ملاحظات متابعة بعد.','No audit events yet.':'لا توجد أحداث تدقيق بعد.',
    'Parties':'الأطراف','Role':'الدور','Logo':'الشعار','Create':'إنشاء','Add Party':'إضافة طرف',
    'Name (EN)':'الاسم (EN)','Name (AR)':'الاسم (AR)','Optional notes…':'ملاحظات اختيارية…',
    'Search projects…':'البحث في المشاريع…','Open →':'فتح ←','Create First Project':'إنشاء أول مشروع',
    'Project code and name are required.':'رمز المشروع واسمه مطلوبان.','Email or username is required':'البريد الإلكتروني أو اسم المستخدم مطلوب',
    'Permissions saved':'تم حفظ الصلاحيات','Employee added':'تمت إضافة الموظف','Employee removed':'تمت إزالة الموظف',
    'Comment added':'تمت إضافة الملاحظة','Project closed':'تم إغلاق المشروع','Project reopened':'تمت إعادة فتح المشروع'
  };
  Object.assign(phrases,{
    'English':'English','Logout':'تسجيل الخروج','Hide Dashboard':'إخفاء الملخص','All Letters':'جميع الكتب',
    'Received':'مستلم','Replied':'تمت الإجابة','For Reference':'للمرجع','Sent':'مرسل','Loading letters…':'جارٍ تحميل الكتب…',
    'New Archive':'أرشيف جديد','Save Archive':'حفظ الأرشيف','Save Letter':'حفظ الكتاب','Archive Number':'رقم الأرشيف',
    'Direction':'الاتجاه','Incoming Letter':'كتاب وارد','Outgoing Letter':'كتاب صادر','Auto Reference Code':'رمز المرجع التلقائي',
    'Subject / Headline':'الموضوع / العنوان','From / Sender':'من / المرسل','To / Recipient':'إلى / المستلم',
    'Letter Date':'تاريخ الكتاب','Received Date (optional)':'تاريخ الاستلام (اختياري)','RECEIVED DATE (optional)':'تاريخ الاستلام (اختياري)','Original Letter No.':'رقم الكتاب الأصلي',
    'Notes / Action Required':'الملاحظات / الإجراء المطلوب','Attach Files (multiple files allowed)':'إرفاق الملفات (يمكن اختيار عدة ملفات)',
    'Attach File (optional)':'إرفاق ملف (اختياري)','ATTACH FILE (optional)':'إرفاق ملف (اختياري)','ATTACH FILES (multiple files allowed)':'إرفاق الملفات (يسمح بعدة ملفات)','Search by code, subject or sender…':'البحث بالرمز أو الموضوع أو المرسل…',
    'New Daily Report':'تقرير يومي جديد','All Weather':'جميع حالات الطقس','Sunny':'مشمس','Partly Cloudy':'غائم جزئياً',
    'Cloudy':'غائم','Windy':'عاصف','Light Rain':'أمطار خفيفة','Rain':'ممطر','Heavy Rain':'أمطار غزيرة',
    'Dust / Sandstorm':'غبار / عاصفة ترابية','Extreme Heat':'حرارة شديدة','Fog':'ضباب','Report Date':'تاريخ التقرير',
    'Weather Notes':'ملاحظات الطقس','Engineers':'المهندسون','Laborers':'العمال','Technicians':'الفنيون','Other':'أخرى',
    'Prepared By':'أعده','Reviewed By':'راجعه','Save Daily Report':'حفظ التقرير اليومي','Delete':'حذف',
    'Search any field — weather, notes, date, code, visitor…':'البحث في الطقس أو الملاحظات أو التاريخ أو الرمز أو الزائر…',
    'New Letter':'كتاب جديد','New Drawing Submission':'إرسال مخطط جديد','New Field Inspection Request':'طلب فحص موقعي جديد',
    'New Material Inspection Request':'طلب فحص مواد جديد','New Method Statement':'بيان تنفيذ عمل جديد',
    'New Request for Information':'طلب معلومات جديد','Search by code, title or area...':'البحث بالرمز أو العنوان أو المنطقة...',
    'Approved with Notes':'مصادق عليه مع ملاحظات','Not Approved':'غير مصادق عليه','Make Corrections':'إجراء التصحيحات',
    'Submittal Date':'تاريخ التقديم','Document Number':'رقم المستند','Inspection Title':'عنوان الفحص',
    'Inspection Description':'وصف الفحص','Material / Inspection Title':'عنوان المادة / الفحص','Method Statement Title':'عنوان بيان التنفيذ',
    'Method Description':'وصف طريقة التنفيذ','RFI Title':'عنوان RFI','Information / Clarification Needed':'المعلومات / الإيضاح المطلوب',
    'Drawing Title':'عنوان المخطط','Drawing Description':'وصف المخطط','Location / Area':'الموقع / المنطقة',
    'Responsible Engineer':'المهندس المسؤول','Related Drawings / Refs':'المخططات / المراجع ذات الصلة',
    'Submitted To (Consultant)':'مقدم إلى (الاستشاري)','CC (Client)':'نسخة إلى (صاحب العمل)','Outcome':'النتيجة',
    'Still Pending — no response yet':'قيد الانتظار — لا توجد إجابة بعد','Submit Drawing Submission':'تقديم المخطط',
    'Submit Field Inspection Request':'تقديم طلب الفحص الموقعي','Submit Material Inspection Request':'تقديم طلب فحص المواد',
    'Submit Method Statement':'تقديم بيان التنفيذ','Submit Request for Information':'تقديم طلب المعلومات',
    'Rev. A — First submission':'المراجعة A — التقديم الأول','Search description, category, amount…':'البحث في الوصف أو الفئة أو المبلغ…',
    'From DD/MM/YYYY':'من يوم/شهر/سنة','To DD/MM/YYYY':'إلى يوم/شهر/سنة','Choose From date':'اختيار تاريخ البداية','Choose To date':'اختيار تاريخ النهاية','Clear':'مسح','Received From':'مستلم من','Paid To':'مدفوع إلى',
    'Add Task':'إضافة فعالية','Print / PDF':'طباعة / PDF','Undo':'تراجع','Day':'يوم','Week':'أسبوع','Month':'شهر',
    'Today':'اليوم','Fit All':'ملاءمة الكل','Expand All':'توسيع الكل','Collapse All':'طي الكل','Indent':'إزاحة للداخل',
    'Outdent':'إزاحة للخارج','Down':'أسفل','Critical Path':'المسار الحرج','Full':'ملء الشاشة','Multi-Select':'تحديد متعدد',
    'Delete Selected':'حذف المحدد','Quick add — type name and Enter':'إضافة سريعة — اكتب الاسم واضغط Enter',
    'Task':'فعالية','Group / Phase':'مجموعة / مرحلة','Sub-Group':'مجموعة فرعية','Responsible':'المسؤول','Assigned To':'مسند إلى',
    'Unassigned':'غير مسند','Name or team':'الاسم أو الفريق','Task Name':'اسم الفعالية','Start':'البدء','Finish':'الانتهاء','Pred':'السابق',
    'New LBTOUT':'إنشاء LBTOUT','New LBTIN':'إنشاء LBTIN','All Tests':'جميع الفحوصات','Sent Sample':'عينة مرسلة',
    'Results':'النتائج','All Results':'جميع النتائج','Pass':'ناجح','Fail':'فاشل','Sample Date':'تاريخ العينة',
    'Material / Sample':'المادة / العينة','Test Type':'نوع الفحص','Testing Lab':'المختبر الفاحص','Sample Location':'موقع العينة',
    'Sample Ref. No.':'رقم مرجع العينة','Quantity / Count':'الكمية / العدد','Save LBTOUT':'حفظ LBTOUT','Result Date':'تاريخ النتيجة',
    'Related LBTOUT (Sent Sample)':'LBTOUT المرتبط (العينة المرسلة)','Required Value':'القيمة المطلوبة','Actual Value':'القيمة الفعلية',
    'Print':'طباعة','Close':'إغلاق','Save Signature':'حفظ التوقيع','Signer name':'اسم الموقّع','Name of the person signing':'اسم الشخص الموقّع',
    'Contract Detail':'تفاصيل العقد','Value / Notes':'القيمة / الملاحظات','Company name':'اسم الشركة','Project name':'اسم المشروع',
    'Contract reference no.':'رقم مرجع العقد','Add Extension':'إضافة تمديد','Work Item Description':'وصف فقرة العمل',
    'Unit Price (IQD)':'سعر الوحدة (IQD)','Add Work Item':'إضافة فقرة عمل','Add VO Item':'إضافة فقرة أمر تغييري',
    'VO Date':'تاريخ الأمر التغييري','Extra Days':'الأيام الإضافية','Add Item':'إضافة فقرة','Section Header':'عنوان قسم','Sub-Item':'فقرة فرعية',
    'Description…':'الوصف…','Category':'الفئة','Company':'الشركة','Client name':'اسم صاحب العمل','Any special contract rules...':'أي شروط عقد خاصة...'
  });
  Object.assign(phrases,{
    'Brief description of letter subject…':'وصف مختصر لموضوع الكتاب…','Organization or person':'الجهة أو الشخص',
    'DD/MM/YYYY':'يوم/شهر/سنة','Received Date (optional)':'تاريخ الاستلام (اختياري)','CC (separate by comma)':'نسخة إلى (افصل بفاصلة)',
    'Any important notes or required actions…':'أي ملاحظات مهمة أو إجراءات مطلوبة…','Name of the archived document…':'اسم المستند المؤرشف…',
    'Attach Files (multiple files allowed)':'إرفاق الملفات (يسمح بعدة ملفات)','Attach File (optional)':'إرفاق ملف (اختياري)',
    '☀️ Sunny':'☀️ مشمس','⛅ Partly Cloudy':'⛅ غائم جزئياً','☁️ Cloudy':'☁️ غائم','💨 Windy':'💨 عاصف',
    '🌦️ Light Rain':'🌦️ أمطار خفيفة','🌧️ Rain':'🌧️ ممطر','⛈️ Heavy Rain':'⛈️ أمطار غزيرة',
    '🌫️ Dust / Sandstorm':'🌫️ غبار / عاصفة ترابية','🌡️ Extreme Heat':'🌡️ حرارة شديدة','🌁 Fog':'🌁 ضباب',
    'Visitor name':'اسم الزائر','Organization or role':'الجهة أو الصفة','Describe a work item completed today...':'صف عملاً أُنجز اليوم...',
    'Describe the planned work for tomorrow...':'صف العمل المخطط للغد...','Any incidents, delays, issues, or remarks...':'أي حوادث أو تأخيرات أو مشكلات أو ملاحظات...',
    'Engineer name':'اسم المهندس','Site manager or PM name':'اسم مدير الموقع أو مدير المشروع','Edit':'تعديل',
    'Code or symbol — e.g. GBP, SAR, ₺, £':'الرمز — مثال: GBP أو SAR أو ₺ أو £','calculated':'محسوب','pending actual finish':'بانتظار الإنجاز الفعلي',
    'Add Custom Unit…':'إضافة وحدة مخصصة…','VO description':'وصف أمر التغيير','Addition':'إضافة','Lump Sum':'مبلغ مقطوع',
    'Monthly Invoice':'فاتورة شهرية','Other (Custom)':'أخرى (مخصص)','Advance Payment':'دفعة مقدمة','Retention':'استقطاع ضمان',
    'Tax (default)':'الضريبة (افتراضي)','Mark as Final':'تعيين كنهائي','Partial':'جزئي','Manual Entry':'إدخال يدوي','View / Edit Items':'عرض / تعديل الفقرات',
    'Cumulative Work Done — This Payment':'الأعمال التراكمية المنجزة — هذه الدفعة','Cumulative Work Done — All Previous Payments':'الأعمال التراكمية المنجزة — جميع الدفعات السابقة',
    'All Categories':'جميع الفئات','Show All':'عرض الكل','Print':'طباعة','Holiday':'عطلة','Weather':'أحوال جوية','Administrative':'إداري',
    'Parent Container':'الحاوية الرئيسية','Standalone / Top Level':'مستقل / مستوى أعلى','% Completion':'نسبة الإنجاز',
    'Predecessors (Finish-to-Start)':'السوابق (إنهاء إلى بدء)','Select predecessor':'اختر السابق','Add Predecessor':'إضافة سابق',
    'Bar Color':'لون الشريط','Optional notes...':'ملاحظات اختيارية...','Days':'الأيام','Milestone ◆':'علامة مرحلية ◆',
    'Response Date':'تاريخ الرد','Responded By':'تم الرد بواسطة','Consultant / Client name':'اسم الاستشاري / صاحب العمل',
    'Response Notes / Comments':'ملاحظات / تعليقات الرد','Comments, conditions, or reasons for rejection...':'التعليقات أو الشروط أو أسباب الرفض...',
    'Save Response':'حفظ الرد','Make Required Corrections':'إجراء التصحيحات المطلوبة','Approved with Notes 📝':'مصادق عليه مع ملاحظات 📝',
    'Not Approved ✗':'غير مصادق عليه ✗','Make Required Corrections ✎':'إجراء التصحيحات المطلوبة ✎',
    'Any additional notes...':'أي ملاحظات إضافية...','Consultant company or engineer name':'اسم شركة الاستشاري أو المهندس',
    'Client name — receives copy only':'اسم صاحب العمل — يستلم نسخة فقط','Describe the completed work and what inspection is being requested...':'صف العمل المنجز والفحص المطلوب...',
    'Describe the material and what inspection is being requested...':'صف المادة والفحص المطلوب...',
    'Describe the method, scope of work, and procedure...':'صف الطريقة ونطاق العمل والإجراء...',
    'Describe the information or clarification needed from the consultant or client...':'صف المعلومات أو الإيضاح المطلوب من الاستشاري أو صاحب العمل...',
    'Search by code, material or lab...':'البحث بالرمز أو المادة أو المختبر...','Select the sent sample this result belongs to':'اختر العينة المرسلة المرتبطة بهذه النتيجة',
    'Pending — awaiting result':'قيد الانتظار — بانتظار النتيجة','Unit':'الوحدة','Result Notes / Comments':'ملاحظات / تعليقات النتيجة',
    'Comments, recommendations...':'التعليقات والتوصيات...','Save LBTIN':'حفظ LBTIN','Sent':'مرسل','Results':'النتائج'
  });
  Object.assign(phrases,{
    'e.g. Ministry of Electricity, Site Engineer':'مثال: وزارة الكهرباء، مهندس الموقع','e.g. APS/2024/001':'مثال: APS/2024/001',
    'e.g. Temperature 42°C, dust storm from 2pm...':'مثال: درجة الحرارة ٤٢°م، عاصفة ترابية من الساعة ٢ ظهراً...',
    'e.g. Excavation Works':'مثال: أعمال الحفر','e.g. Road Layout Plan — Level 1':'مثال: مخطط الطرق — الطابق ١',
    'e.g. Shop drawings for reinforced concrete columns, Level 1...':'مثال: مخططات تنفيذية لأعمدة الخرسانة المسلحة، الطابق ١...',
    'e.g. Foundation Rebar Inspection — Grid A-B':'مثال: فحص حديد تسليح الأساس — المحاور A-B',
    'e.g. Reinforcement Steel Bars — Grade 60':'مثال: قضبان حديد التسليح — درجة ٦٠',
    'e.g. Concrete Pouring Method for Foundation Slab':'مثال: طريقة صب خرسانة حصيرة الأساس',
    'e.g. Clarification on Foundation Depth at Grid C-4':'مثال: إيضاح عمق الأساس عند المحور C-4',
    'e.g. Grid A-B / Zone 1':'مثال: المحاور A-B / المنطقة ١','e.g. Zone 1 / Grid A-B':'مثال: المنطقة ١ / المحاور A-B',
    'e.g. Concrete Cube, Rebar, Sand':'مثال: مكعب خرساني، حديد تسليح، رمل',
    'e.g. Compressive Strength, Sieve Analysis':'مثال: مقاومة الانضغاط، التحليل المنخلي',
    'e.g. Grid A-B, Level 1':'مثال: المحاور A-B، الطابق ١','e.g. 3 cubes':'مثال: ٣ مكعبات',
    'e.g. ≥ 25 MPa':'مثال: ≥ ٢٥ MPa','e.g. 28.4 MPa':'مثال: ٢٨٫٤ MPa',
    'Record Response':'تسجيل الرد','Select the sent sample this result belongs to':'اختر العينة المرسلة المرتبطة بهذه النتيجة',
    'Category':'الفئة','Quantity':'الكمية','Auto from BOQ total':'تلقائي من إجمالي جدول الكميات',
    'Auto from VO section':'تلقائي من قسم أوامر التغيير','Auto = Contract Value + VO':'تلقائي = قيمة العقد + أوامر التغيير',
    'Add ذرعة / Payment Request':'إضافة ذرعة / طلب دفعة','Standalone / Top Level':'مستقل / مستوى أعلى','Hide':'إخفاء'
  });
  const lowerPhrases=Object.fromEntries(Object.entries(phrases).map(([key,value])=>[key.toLowerCase(),value]));
  const originals=new WeakMap();
  const attrOriginals=new WeakMap();
  const protectedSelector='input,textarea,[contenteditable],.user-content,.project-name,.party-name,.description-cell,[data-binna-sidebar-toggle]';
  function translatePhrase(value,arabic){
    const source=String(value==null?'':value),trimmed=source.trim(),required=/\s*\*$/.test(trimmed),prefix=(trimmed.match(/^[^A-Za-z0-9\u0600-\u06ff]+\s*/)||[''])[0],core=trimmed.replace(/\s*\*$/,'').slice(prefix.length).trim();
    if(!arabic)return source;
    let translated=phrases[trimmed]||lowerPhrases[trimmed.toLowerCase()]||phrases[core]||lowerPhrases[core.toLowerCase()];
    if(!translated&&/^e\.g\.\s*/i.test(core))translated='مثال: '+core.replace(/^e\.g\.\s*/i,'');
    if(!translated&&/^Rev\.\s*[A-Z]$/i.test(core))translated='المراجعة '+core.slice(-1);
    if(!translated){const decorated=core.match(/^(.+?)\s*([✓✗✎◆])$/);if(decorated){const base=phrases[decorated[1]]||lowerPhrases[decorated[1].toLowerCase()];if(base)translated=base+' '+decorated[2];}}
    if(!translated){const abbreviation=core.match(/^(LBTOUT|LBTIN)\s+—\s+(Sent|Results)$/);if(abbreviation)translated=abbreviation[1]+' — '+(phrases[abbreviation[2]]||abbreviation[2]);}
    return translated?(prefix+translated+(required?' *':'')):source;
  }
  function translateText(node,arabic){
    if(!node.parentElement||node.parentElement.closest(protectedSelector))return;
    const raw=originals.has(node)?originals.get(node):node.nodeValue;
    if(!originals.has(node))originals.set(node,raw);
    const leading=(raw.match(/^\s*/)||[''])[0],trailing=(raw.match(/\s*$/)||[''])[0];
    const core=raw.trim();
    if(!core)return;
    let translated=translatePhrase(core,arabic);
    if(arabic&&translated===core){
      translated=translated
        .replace(/^Total Income:/i,'إجمالي الإيرادات:')
        .replace(/^Total Expenses:/i,'إجمالي المصروفات:')
        .replace(/^Total Paid:/i,'إجمالي المدفوع:')
        .replace(/^Balance:/i,'الرصيد:')
        .replace(/^Payment\s+(\d+)/i,'دفعة $1')
        .replace(/^(\d+) total$/i,'$1 إجمالي')
        .replace(/^\(total\s+(\d+)\)$/i,'(الإجمالي $1)')
        .replace(/^(\d+) projects?$/i,'$1 مشروع')
        .replace(/^👤\s*(\d+) members?$/i,'👤 $1 عضو')
        .replace(/^No entries yet/i,'لا توجد قيود بعد')
        .replace(/^No records/i,'لا توجد سجلات');
    }
    if(arabic&&translated!==core&&!/[A-Z]{2,}[-/]\d/.test(core))translated=BINNA_I18N.toArabicDigits(translated);
    if(arabic&&node.parentElement.matches('.row-num,.num,.mono,.mono-in,.metric,.stat,.pagination button,[data-localized-number]'))translated=BINNA_I18N.toArabicDigits(translated);
    if(arabic&&/^[+−-]?[\d\s.,٬٫%]+(?:\s*(?:IQD|USD|EUR|days?))?$/.test(core))translated=BINNA_I18N.toArabicDigits(translated);
    node.nodeValue=leading+translated+trailing;
  }
  function translateAttrs(el,arabic){
    if(el.matches('[data-binna-sidebar-toggle]'))return;
    if(!attrOriginals.has(el))attrOriginals.set(el,{});
    const saved=attrOriginals.get(el);
    ['placeholder','title','aria-label'].forEach(attr=>{
      if(el.hasAttribute(attr)&&saved[attr]===undefined)saved[attr]=el.getAttribute(attr);
      if(saved[attr]!==undefined)el.setAttribute(attr,translatePhrase(saved[attr],arabic));
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
  global.BINNA_OPERATIONAL_I18N={localize,phrases,translatePhrase};
})(window);
