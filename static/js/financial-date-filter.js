(function(global){
  'use strict';

  const DIGITS='٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹';
  function normalizeDigits(value){
    return String(value==null?'':value).replace(/[٠-٩۰-۹]/g,digit=>{
      const index=DIGITS.indexOf(digit);
      return String(index<10?index:index-10);
    });
  }
  function parseDate(value){
    const normalized=normalizeDigits(value).trim();
    if(!normalized)return null;
    let year,month,day;
    let match=normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(match){year=Number(match[1]);month=Number(match[2]);day=Number(match[3]);}
    else{
      match=normalized.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
      if(!match)return null;
      day=Number(match[1]);month=Number(match[2]);year=Number(match[3]);
    }
    const date=new Date(Date.UTC(year,month-1,day));
    if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day)return null;
    return String(year).padStart(4,'0')+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0');
  }
  function bounds(fromValue,toValue){
    const hasFrom=String(fromValue||'').trim()!=='';
    const hasTo=String(toValue||'').trim()!=='';
    if(!hasFrom&&!hasTo)return {valid:true,from:null,to:null};
    const from=hasFrom?parseDate(fromValue):null,to=hasTo?parseDate(toValue):null;
    if((hasFrom&&!from)||(hasTo&&!to))return {valid:false,from:null,to:null};
    if(from&&to&&from>to)return {valid:false,from,to};
    const exact=from||to;
    return {valid:true,from:from&&to?from:exact,to:from&&to?to:exact};
  }
  function filterRows(rows,fromValue,toValue){
    const range=bounds(fromValue,toValue);
    if(!range.valid)return [];
    if(!range.from&&!range.to)return Array.from(rows||[]);
    return Array.from(rows||[]).filter(row=>row&&row.date&&row.date>=range.from&&row.date<=range.to);
  }
  function formatDisplay(iso,arabic){
    const parsed=parseDate(iso);
    if(!parsed)return '';
    const parts=parsed.split('-'),display=parts[2]+'/'+parts[1]+'/'+parts[0];
    return arabic?display.replace(/\d/g,d=>'٠١٢٣٤٥٦٧٨٩'[Number(d)]):display;
  }
  function syncPicker(calendarInput,textInput,arabic){
    const iso=parseDate(calendarInput&&calendarInput.value);
    if(textInput)textInput.value=iso?formatDisplay(iso,arabic):'';
    return iso;
  }
  global.BINNA_FINANCIAL_DATES={normalizeDigits,parseDate,bounds,filterRows,formatDisplay,syncPicker};
})(window);
