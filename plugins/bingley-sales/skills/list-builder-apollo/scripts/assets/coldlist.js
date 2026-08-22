<script id="coldlist-js">
const DATA=__DATA_JSON__;
const XLSX_B64="__XLSX_B64__";
const CFG=__CFG_JSON__;
const norm=s=>(s==null?"":String(s)).trim();
const esc=s=>norm(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
const cur=CFG.currency||"";
const REV_LABELS=["Under "+cur+"5M",cur+"5M–"+cur+"10M",cur+"10M–"+cur+"25M",cur+"25M+","Not disclosed"];
function revIdx(raw){var v=norm(raw);if(!v||/unknown/i.test(v))return 4;var nums=(v.match(/\d+(\.\d+)?/g)||[]).map(Number);if(!nums.length)return 4;var top=Math.max.apply(null,nums);if(/[<]/.test(v)&&nums.length===1)top=nums[0];if(/\+/.test(v)&&nums.length===1&&top<26)top=26;if(top<=5)return 0;if(top<=10)return 1;if(top<=25)return 2;return 3;}
function cleanRev(v){v=norm(v);if(!v||/unknown/i.test(v))return "";return v.replace(/~/g,"").replace(/\(est\)/ig,"").replace(/\s+/g," ").trim().replace(/-/g,"–");}
function sizeBand(e){const x=parseFloat(e);if(isNaN(x))return "Unknown";if(x<=10)return "1–10";if(x<=20)return "11–20";if(x<=50)return "21–50";if(x<=100)return "51–100";return "100+";}
const SIZE_ORDER=["1–10","11–20","21–50","51–100","100+","Unknown"];
function seniority(t){t=norm(t).toLowerCase();if(!t)return "Other";
  if(/founder|owner|proprietor/.test(t))return "Owner / Founder";
  if(/partner/.test(t))return "Partner";
  if(/chief|\bc[efmoprt]o\b|president|managing director|\bmd\b|head of|vice president|\bvp\b|director|principal/.test(t))return "Director / Exec";
  return "Other / Senior";}
const LOCKSVG='<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px"><rect x="5" y="11" width="14" height="9" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>';
const LOCKPILL='<span class="cl-lock" title="Enrich to reveal LinkedIn">'+LOCKSVG+' Enrich</span>';
function liUrl(d){return norm(d._li);}
const mxLab=l=>({M365:"M365",GATEWAY:"Gateway",GOOGLE:"Google",OTHER:"Other",NO_MX:"No MX"})[l]||l;
DATA.forEach(d=>{d._revi=revIdx(d["Rev Band"]);d._revc=cleanRev(d["Rev Band"]);d._size=sizeBand(d.Employees);d._sen=seniority(d.Title);});

// header meta
(function(){const comp=new Set(DATA.map(d=>norm(d.Company))).size;const em=DATA.filter(d=>norm(d.Email)).length;
  const geo=CFG.geo?" · "+CFG.geo:"";
  document.getElementById("cl-meta").innerHTML="<b>"+DATA.length+"</b> prospects · <b>"+comp+"</b> companies"+(em===DATA.length&&em?" · <b>100%</b> verified email":"")+geo;})();

function bars(ent,colorFn){const max=Math.max(...ent.map(e=>e[1]),1);
  return ent.map(([lab,nn])=>'<div class="cl-bar"><div class="lab" title="'+esc(lab)+'">'+esc(lab)+'</div><div class="track"><div class="fill" style="width:'+Math.round(nn/max*100)+'%;background:'+(colorFn?colorFn(lab):"var(--navy)")+'"></div></div><div class="v">'+nn+'</div></div>').join("");}
function dist(getter,order,colorFn){const c={};DATA.forEach(d=>{const v=getter(d);if(v==null)return;c[v]=(c[v]||0)+1;});let ent=order?order.filter(o=>c[o]).map(o=>[o,c[o]]):Object.entries(c).sort((a,b)=>b[1]-a[1]);return bars(ent,colorFn);}
const revCol=l=>{const i=REV_LABELS.indexOf(l);return ["var(--slate)","#4b78d6","#3D6FD0","#21407A","#c9c2bb"][i]||"var(--navy)";};
function hide(id){const e=document.getElementById(id);if(e)e.remove();}

// boxes with degradation
if(CFG.show.rev)document.getElementById("d-rev").innerHTML=dist(d=>REV_LABELS[d._revi],REV_LABELS,revCol);else hide("box-rev");
if(CFG.show.size)document.getElementById("d-size").innerHTML=dist(d=>d._size,SIZE_ORDER);else hide("box-size");
if(CFG.show.sen)document.getElementById("d-sen").innerHTML=dist(d=>d._sen);else hide("box-sen");

function fillSel(id,vals,all){const el=document.getElementById(id);if(!el)return;el.innerHTML='<option value="">'+all+'</option>'+vals.map(v=>'<option>'+esc(v)+'</option>').join("");}
if(CFG.show.rev)fillSel("f-rev",REV_LABELS.filter(r=>DATA.some(d=>REV_LABELS[d._revi]===r)),"All revenue");else hide("f-rev");
if(CFG.show.size)fillSel("f-size",SIZE_ORDER.filter(s=>DATA.some(d=>d._size===s)),"All sizes");else hide("f-size");
if(CFG.show.sen)fillSel("f-sen",[...new Set(DATA.map(d=>d._sen))],"All roles");else hide("f-sen");
if(CFG.show.mx)fillSel("f-mx",[...new Set(DATA.map(d=>mxLab(norm(d["MX Status"]))).filter(Boolean))],"All inboxes");else hide("f-mx");

const COLS=[
 {label:"Company",w:"24%",key:d=>norm(d.Company),cell:d=>{const w=norm(d._web);const nm=esc(d.Company);const co='<span class="cl-co">'+(w?'<a href="'+esc(w)+'" target="_blank" rel="noopener">'+nm+'</a>':nm)+'</span>';return '<div class="cl-corow"><span class="cl-caret">&#9656;</span>'+co+'</div>';}},
 {label:"Contact",w:"16%",key:d=>norm(d["Contact Name"]),cell:d=>'<div class="cl-contact"><div class="nm">'+esc(d["Contact Name"])+'</div><div class="rl">'+esc(d.Title)+'</div></div>'},
 {label:"Email",w:"13%",key:d=>norm(d.Email),cell:d=>{const e=norm(d.Email);return '<span class="cl-email" title="'+esc(e)+'">'+(e?'<a href="mailto:'+esc(e)+'">'+esc(e)+'</a>':'&mdash;')+'</span>';}},
 {label:"In",w:"13%",sort:false,cls:"ctr",cell:d=>{const real=norm(d._li);return real?('<a class="cl-li" href="'+esc(real)+'" target="_blank" rel="noopener" title="LinkedIn profile">in</a>'):LOCKPILL;}},
 {label:"Staff",w:"8%",num:true,cls:"r",key:d=>{const x=parseFloat(d.Employees);return isNaN(x)?Infinity:x;},cell:d=>'<span>'+(norm(d.Employees)||'&mdash;')+'</span>'},
 {label:"Revenue",w:"13%",key:d=>d._revi,cell:d=>d._revi===4?'<span class="cl-dim">Not disclosed</span>':esc(REV_LABELS[d._revi]),show:()=>CFG.show.rev},
 {label:"MX",w:"13%",key:d=>norm(d["MX Status"]),cell:d=>{const v=norm(d["MX Status"]);if(!v)return '&mdash;';const cls={M365:"m365",GATEWAY:"gateway",GOOGLE:"google",OTHER:"other",NO_MX:"no_mx"}[v]||"other";return '<span class="cl-pill '+cls+'">'+esc(mxLab(v))+'</span>';},show:()=>CFG.show.mx}
].filter(c=>!c.show||c.show());

const head=document.getElementById("head");
COLS.forEach((c,i)=>{const th=document.createElement("th");let cl=(c.cls?c.cls+" ":"")+(c.sort===false?"nos":"");th.className=cl.trim();th.innerHTML=esc(c.label)+(c.sort===false?"":' <span class="ar" data-i="'+i+'"></span>');if(c.sort!==false)th.onclick=()=>sortBy(i);head.appendChild(th);});
(function(){const tbl=document.querySelector(".cl-table");if(!tbl)return;const cg=document.createElement("colgroup");COLS.forEach(c=>{const co=document.createElement("col");if(c.w)co.style.width=c.w;cg.appendChild(co);});tbl.insertBefore(cg,tbl.firstChild);})();

let sortIdx=0,sortDir=1,filtered=DATA.slice();
function rowHTML(d,i){return '<tr class="row'+(i%2?' alt':'')+'" data-idx="'+DATA.indexOf(d)+'">'+COLS.map(c=>'<td'+(c.cls?' class="'+c.cls+'"':'')+'>'+c.cell(d)+'</td>').join("")+'</tr>';}
function detailHTML(d){const f=[["Revenue band (raw)","_revc"],["Company phone","Company Phone"],["Source","Source"],["MX provider","MX Provider"],["Run date","Run Date"],["Notes","Notes"],["Background","Background"]];
  const _liR=norm(d._li);const _liCell=_liR?('<a href="'+esc(_liR)+'" target="_blank" rel="noopener">open profile &rarr;</a>'):('<span class="cl-lockx">'+LOCKSVG+' Enrich to reveal</span>');
  let cells='<div class="cl-kv"><div class="k">LinkedIn</div><div class="v2">'+_liCell+'</div></div>';
  cells+=f.filter(x=>norm(d[x[1]])).map(x=>{const full=(x[1]==="Background"||x[1]==="Notes")?" full":"";return '<div class="cl-kv'+full+'"><div class="k">'+x[0]+'</div><div class="v2">'+esc(d[x[1]])+'</div></div>';}).join("");
  return '<tr class="detail"><td colspan="'+COLS.length+'"><div class="cl-detail">'+cells+'</div></td></tr>';}
function render(){const tb=document.getElementById("body");
  if(!filtered.length){tb.innerHTML='<tr><td colspan="'+COLS.length+'"><div class="cl-empty">No prospects match these filters.</div></td></tr>';document.getElementById("count").textContent="0 of "+DATA.length;document.getElementById("rowcapnote").style.display="none";return;}
  const cap=CFG.rowCap||100000;const slice=filtered.slice(0,cap);
  tb.innerHTML=slice.map((d,i)=>rowHTML(d,i)).join("");
  document.getElementById("count").textContent=filtered.length+" of "+DATA.length;
  const note=document.getElementById("rowcapnote");if(filtered.length>cap){note.style.display="block";note.textContent="Showing first "+cap+" of "+filtered.length+" — filter to narrow, or Download Excel for the full list.";}else note.style.display="none";
  document.querySelectorAll(".ar").forEach(a=>a.textContent="");const el=document.querySelector('.ar[data-i="'+sortIdx+'"]');if(el)el.textContent=sortDir>0?"▲":"▼";}
function doSort(){const col=COLS[sortIdx];if(!col||!col.key)return;filtered.sort((a,b)=>{let x=col.key(a),y=col.key(b);if(col.num||typeof x==="number")return ((x===y)?0:(x<y?-1:1))*sortDir;return String(x).localeCompare(String(y))*sortDir;});}
function sortBy(i){if(sortIdx===i)sortDir*=-1;else{sortIdx=i;sortDir=1;}doSort();render();}
function applyFilters(){const q=document.getElementById("q").value.toLowerCase().trim();
  const gv=id=>{const e=document.getElementById(id);return e?e.value:"";};
  const fr=gv("f-rev"),fs=gv("f-size"),fn=gv("f-sen"),fm=gv("f-mx");
  filtered=DATA.filter(d=>{if(fr&&REV_LABELS[d._revi]!==fr)return false;if(fs&&d._size!==fs)return false;if(fn&&d._sen!==fn)return false;if(fm&&mxLab(norm(d["MX Status"]))!==fm)return false;
    if(q){const b=(norm(d.Company)+" "+norm(d["Contact Name"])+" "+norm(d.Email)+" "+norm(d.Title)+" "+REV_LABELS[d._revi]+" "+norm(d["MX Status"])).toLowerCase();if(b.indexOf(q)<0)return false;}return true;});doSort();render();}
document.getElementById("body").addEventListener("click",e=>{const tr=e.target.closest("tr.row");if(!tr)return;if(e.target.tagName==="A")return;
  const open=tr.classList.contains("open");document.querySelectorAll("tr.row.open").forEach(r=>{r.classList.remove("open");if(r.nextSibling&&r.nextSibling.classList&&r.nextSibling.classList.contains("detail"))r.nextSibling.remove();});
  if(!open){tr.classList.add("open");tr.insertAdjacentHTML("afterend",detailHTML(DATA[+tr.dataset.idx]));}});
["input","change"].forEach(ev=>{document.getElementById("q").addEventListener(ev,applyFilters);["f-rev","f-size","f-sen","f-mx"].forEach(id=>{const e=document.getElementById(id);if(e)e.addEventListener(ev,applyFilters);});});
document.getElementById("reset").onclick=()=>{document.getElementById("q").value="";["f-rev","f-size","f-sen","f-mx"].forEach(id=>{const e=document.getElementById(id);if(e)e.value="";});sortIdx=1;sortDir=1;applyFilters();};
// download
(function(){var dl=document.getElementById("dl"),note=document.getElementById("dlnote");
  if(!(CFG.dl.mode==="embed"&&XLSX_B64)){dl.classList.add("cl-dl-file");dl.innerHTML='<span class="ic">&#10515;</span> Excel in your folder';dl.removeAttribute("href");dl.title=CFG.dl.name+" (too large to embed)";if(note)note.textContent="See file link in chat";return;}
  try{var bin=atob(XLSX_B64),n=bin.length,buf=new Uint8Array(n);for(var i=0;i<n;i++)buf[i]=bin.charCodeAt(i);
    var url=URL.createObjectURL(new Blob([buf],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}));
    dl.href=url;dl.download=CFG.dl.name;dl.title="Download "+CFG.dl.name;}
  catch(e){dl.href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"+XLSX_B64;dl.download=CFG.dl.name;dl.title="Download "+CFG.dl.name;}
  if(note)note.textContent="Downloads this list, enriched or not";
  var bridge=window.cowork&&typeof window.cowork.callMcpTool==="function";
  if(bridge&&CFG.dl.path){dl.addEventListener("click",function(ev){ev.preventDefault();var orig=dl.innerHTML;dl.innerHTML='<span class="ic">&#10515;</span> Sending to chat…';
    Promise.resolve(window.cowork.callMcpTool("mcp__cowork__present_files",{files:[{file_path:CFG.dl.path}]}))
      .then(function(){if(note)note.textContent="Excel sent to the chat below";})
      .catch(function(){if(note)note.textContent="File link is in the chat";})
      .finally(function(){dl.innerHTML=orig;});});}
})();
applyFilters();
</script>