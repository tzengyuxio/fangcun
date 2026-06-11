#!/usr/bin/env node
// WNS (UPU/WADP) official stamp DB query via the web-access CDP proxy.
// The wnsstamps.post API blocks non-browser clients (TLS/header fingerprint),
// so we run an in-page synchronous XHR inside the user's Chrome (origin context).
//
// Usage:
//   node query.mjs [--terms STR] [--member NAME] [--year YYYY] [--month N]
//                  [--theme NAME] [--wns WNSNUMBER] [--page-size N] [--page N]
//                  [--sort asc|desc] [--json]
// Examples:
//   node query.mjs --terms zodiac --year 2026
//   node query.mjs --member "Hong Kong" --terms horse
//   node query.mjs --wns SG002.2026
//
// Requires the web-access CDP proxy (http://localhost:3456). If it is not up,
// run:  node ~/.claude/skills/web-access/scripts/check-deps.mjs

import { spawnSync } from 'node:child_process';

const PROXY = 'http://localhost:3456';
const ORIGIN = 'https://wnsstamps.post/?lang=en&SearchType=Partial';

function parseArgs(argv) {
  const a = { terms: '', member: '', year: '-x', month: '-x', theme: '', wns: '', pageSize: '20', page: '0', sort: 'descending', json: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const v = argv[i + 1];
    switch (k) {
      case '--terms': a.terms = v; i++; break;
      case '--member': a.member = v; i++; break;
      case '--year': a.year = v; i++; break;
      case '--month': a.month = v; i++; break;
      case '--theme': a.theme = v; i++; break;
      case '--wns': a.wns = v; i++; break;
      case '--page-size': a.pageSize = v; i++; break;
      case '--page': a.page = v; i++; break;
      case '--sort': a.sort = v === 'asc' ? 'ascending' : 'descending'; i++; break;
      case '--json': a.json = true; break;
    }
  }
  return a;
}

async function proxy(path, opts = {}) {
  const r = await fetch(PROXY + path, opts);
  return r.json();
}

async function ensureProxy() {
  try {
    const r = await fetch(PROXY + '/targets', { signal: AbortSignal.timeout(4000) });
    if (r.ok) return true;
  } catch { /* fall through */ }
  // try to start the web-access proxy
  const dep = `${process.env.HOME}/.claude/skills/web-access/scripts/check-deps.mjs`;
  spawnSync('node', [dep], { stdio: 'ignore' });
  try {
    const r = await fetch(PROXY + '/targets', { signal: AbortSignal.timeout(4000) });
    return r.ok;
  } catch { return false; }
}

// JS that runs inside the wnsstamps.post tab (same-origin): resolve filter
// names -> ids, then search. Uses async fetch; the CDP proxy awaits the promise.
function buildEval(a) {
  return `(()=>{
  function get(u){return fetch(u,{headers:{"X-Requested-With":"XMLHttpRequest"}}).then(function(r){return r.json()}).catch(function(){return null});}
  var MEMBER=${JSON.stringify(a.member)}, THEME=${JSON.stringify(a.theme)};
  return Promise.all([
    MEMBER?get("https://wnsstamps.post/Home/autoGetMembers?lang=en"):Promise.resolve(null),
    THEME?get("https://wnsstamps.post/Theme/autoGetThemes?lang=en"):Promise.resolve(null)
  ]).then(function(vv){
    var ms=vv[0], ts=vv[1];
    var memberId="-x", themeId="-x", memberResolved=null, themeResolved=null;
    if(ms&&MEMBER){var f=ms.find(function(m){return m.t.toLowerCase()===MEMBER.toLowerCase()})||ms.find(function(m){return m.t.toLowerCase().indexOf(MEMBER.toLowerCase())>=0});if(f){memberId=f.v;memberResolved=f.t}}
    if(ts&&THEME){var g=ts.find(function(t){return t.text.toLowerCase()===THEME.toLowerCase()})||ts.find(function(t){return t.text.toLowerCase().indexOf(THEME.toLowerCase())>=0});if(g){themeId=g.value;themeResolved=g.text}}
    var p=new URLSearchParams({wNSNumber:${JSON.stringify(a.wns)},member:memberId,allMember:"0",year:${JSON.stringify(a.year)},allYear:"0",ddlmonth:${JSON.stringify(a.month)},allMonth:"0",themeId:themeId,subTheme:"-x",sorting:${JSON.stringify(a.sort)},searchType:"Partial",pageIndex:${JSON.stringify(String(a.page))},pageSize:${JSON.stringify(String(a.pageSize))},termsFilters:${JSON.stringify(a.terms)},setw:"",lang:"en",refine:"true"});
    return get("https://wnsstamps.post/Home/autoStampSearch?"+p.toString()).then(function(r){
      r=r||[];
      return JSON.stringify({memberResolved:memberResolved,themeResolved:themeResolved,count:r.length,results:r.map(function(s){return {wns:s.WNS_NUMBER,date:(s.DATE_OF_ISSUE||"").slice(0,10),subject:s.SUBJECT,member:s.ISSUING_AUTHORITY,w:s.WIDTH,h:s.HEIGHT,denom:s.DENOMINATION,cur:s.CURRENCY,perf:s.PERFORATIONS,printer:s.PRINTER,tech:s.PrintingTechnique,artist:s.Artist,engraver:s.Engraver,qty:s.Quantity,img:s.ImageName?("https://wnsstamps.post/images/T180/"+s.ImageName):null}})});
    });
  });
})()`;
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (!(await ensureProxy())) {
    console.error('✗ CDP proxy 未就緒。請先在 Chrome 開啟遠端偵錯（chrome://inspect/#remote-debugging），\n  或執行: node ~/.claude/skills/web-access/scripts/check-deps.mjs');
    process.exit(1);
  }
  const tab = await proxy('/new?url=' + encodeURIComponent(ORIGIN));
  const tid = tab.targetId;
  // let the SPA settle (anti-bot init) before same-origin API calls
  await new Promise((r) => setTimeout(r, 5000));
  try {
    const res = await proxy('/eval?target=' + tid, { method: 'POST', body: buildEval(a) });
    const data = JSON.parse(res.value);
    if (a.json) { console.log(JSON.stringify(data, null, 2)); return; }
    if (data.memberResolved) console.log(`member → ${data.memberResolved}`);
    if (data.themeResolved) console.log(`theme  → ${data.themeResolved}`);
    console.log(`共 ${data.count} 筆：\n`);
    for (const s of data.results) {
      console.log(`● ${s.wns}  ${s.date}  ${s.subject}`);
      console.log(`   ${s.member} | ${s.denom ?? '?'}${s.cur ?? ''} | ${s.w}×${s.h}mm | 齒孔 ${s.perf || '—'}`);
      console.log(`   印製 ${s.printer || '—'} | ${s.tech || '—'}${s.artist ? ' | 設計 ' + s.artist : ''}${s.qty ? ' | 量 ' + s.qty : ''}`);
      console.log(`   圖 ${s.img || '—'}`);
    }
  } finally {
    await fetch(PROXY + '/close?target=' + tid).catch(() => {});
  }
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
