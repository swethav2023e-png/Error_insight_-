const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const C={Critical:"#ef5260",Error:"#ff9b42",Warning:"#635bff",Info:"#19b9c9"};
function render(d){
 $("total").textContent=d.total;$("types").textContent=d.unique_types;$("critical").textContent=d.critical;$("warning").textContent=d.warning;
 const t=Object.entries(d.type_counts).sort((a,b)=>b[1]-a[1]),max=Math.max(...t.map(x=>x[1]),1);
 $("bars").innerHTML=t.map(([k,v])=>`<div class="bar"><span>${esc(k)}</span><div class="track"><div class="fill" style="width:${v/max*100}%"></div></div><b>${v}</b></div>`).join("");
 let start=0,g=[];Object.entries(d.severity_counts).forEach(([k,v])=>{let end=start+v/Math.max(d.total,1)*100;g.push(`${C[k]||"#aaa"} ${start}% ${end}%`);start=end});
 $("donut").style.background=`conic-gradient(${g.join(",")})`;$("donutTotal").textContent=d.total;
 $("legend").innerHTML=Object.entries(d.severity_counts).map(([k,v])=>`<div><span class="dot" style="background:${C[k]||"#aaa"}"></span><span>${esc(k)}</span><b>${v}</b></div>`).join("");
 $("recurringList").innerHTML=d.recurring.map(x=>`<div class="card"><div class="cardtop"><span>${esc(x.type)}</span><span class="pill ${x.severity}">${esc(x.severity)}</span></div><div class="count">${x.count}</div><small>occurrences detected</small></div>`).join("");
 $("recommendationsList").innerHTML=d.recurring.map(x=>`<div class="recommendation"><h4>✦ ${esc(x.type)}</h4><p><strong>Possible cause:</strong> ${esc(x.cause)}</p><p><strong>Recommended solution:</strong> ${esc(x.solution)}</p></div>`).join("");
 $("recentBody").innerHTML=d.recent.map(x=>`<tr><td>${esc(x.timestamp)}</td><td><b>${esc(x.type)}</b></td><td>${esc(x.message)}</td><td><span class="pill ${x.severity}">${esc(x.severity)}</span></td></tr>`).join("");
 $("health").textContent=d.critical>0?"ATTENTION":"HEALTHY";
}
function message(t,bad=false){$("msg").textContent=t;$("msg").classList.remove("hidden");$("msg").style.color=bad?"#b42318":"#4f46c9";}
async function demo(){try{const r=await fetch("/api/demo"),d=await r.json();render(d);message("Demo dataset loaded — dashboard updated.");}catch(e){message("Could not load demo data.",true)}}
$("demo").onclick=demo;
$("file").onchange=async e=>{const f=e.target.files[0];if(!f)return;const form=new FormData();form.append("file",f);try{const r=await fetch("/api/analyze",{method:"POST",body:form}),d=await r.json();if(!r.ok)throw Error(d.error);render(d);message(f.name+" analyzed successfully.");}catch(e){message(e.message,true)}};
demo();
