import {useEffect,useState,useCallback} from "react"
const API=import.meta.env.VITE_API||"http://localhost:8000"
const TABS=["Sources","Review","Interview","Timeline","Handover","Audit"]
const BADGE={Verified:"bg-green-100 text-green-800",Inferred:"bg-amber-100 text-amber-800",Conflicting:"bg-red-100 text-red-800",Missing:"bg-slate-200 text-slate-700"}
const Badge=({s})=><span className={"px-2 py-0.5 rounded text-xs font-semibold "+BADGE[s]}>{s}</span>
const Card=({children,className=""})=><div className={"bg-white border border-slate-300 rounded-xl p-4 "+className}>{children}</div>
const Btn=({className="bg-[#1f4e79]",...p})=><button className={"px-3 py-1.5 rounded-lg text-sm font-semibold text-white disabled:opacity-40 "+className} {...p}/>

export default function App(){
  const [users,setUsers]=useState([]),[uid,setUid]=useState(1),[tab,setTab]=useState("Review"),[tick,setTick]=useState(0),[err,setErr]=useState("")
  const call=useCallback(async(p,o={})=>{
    const r=await fetch(API+p,{...o,headers:{"Content-Type":"application/json","X-User-Id":String(uid)},body:o.body&&JSON.stringify(o.body)})
    const j=await r.json(); if(!r.ok){setErr(j.detail||"Error");throw new Error(j.detail)} setErr(""); return j
  },[uid])
  const bump=()=>setTick(t=>t+1)
  useEffect(()=>{fetch(API+"/api/users").then(r=>r.json()).then(setUsers)},[])
  const user=users.find(u=>u.id===uid)||{role:"lead"}
  const P={call,user,tick,bump}
  return <div className="min-h-screen bg-slate-50 text-slate-800">
    <header className="bg-white border-b border-slate-300 px-6 py-3 flex items-center gap-4">
      <h1 className="text-2xl font-extrabold">Handover<span className="text-[#1f4e79]">Trail</span></h1>
      <nav className="flex gap-1 flex-1">{TABS.map(t=><button key={t} onClick={()=>setTab(t)} className={"px-3 py-1.5 rounded-lg text-sm font-semibold "+(tab===t?"bg-[#e6b800]":"hover:bg-slate-100")}>{t}</button>)}</nav>
      <select value={uid} onChange={e=>setUid(+e.target.value)} className="border rounded-lg px-2 py-1 text-sm">{users.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select>
    </header>
    {err&&<div className="bg-red-100 text-red-800 px-6 py-2 text-sm">{err}</div>}
    <main className="p-6 max-w-6xl mx-auto">
      {tab==="Sources"&&<Sources {...P}/>}{tab==="Review"&&<Review {...P}/>}{tab==="Interview"&&<Interview {...P}/>}
      {tab==="Timeline"&&<Timeline {...P}/>}{tab==="Handover"&&<Handover {...P}/>}{tab==="Audit"&&<Audit {...P}/>}
    </main></div>
}
const useGet=(path,{call,tick})=>{const [d,setD]=useState(null);useEffect(()=>{call(path).then(setD).catch(()=>{})},[path,call,tick]);return d}

function Sources(P){
  const src=useGet("/api/sources",P)||[],[f,setF]=useState({title:"",kind:"notes",content:"",restricted:false}),[q,setQ]=useState(""),[hits,setHits]=useState([]),[msg,setMsg]=useState("")
  return <div className="grid md:grid-cols-2 gap-4">
    <Card><h2 className="font-bold mb-2">Connect authorised sources</h2>
      <p className="text-xs text-slate-500 mb-2">Use synthetic or anonymised data only. Format: DECISION[topic]: text (owner: Name) · RISK · BLOCKER · DEPENDS · TODO · OPEN</p>
      <input className="border rounded w-full p-2 mb-2 text-sm" placeholder="Title" value={f.title} onChange={e=>setF({...f,title:e.target.value})}/>
      <select className="border rounded p-2 mb-2 text-sm" value={f.kind} onChange={e=>setF({...f,kind:e.target.value})}>{["chat","repo","tasks","notes","doc"].map(k=><option key={k}>{k}</option>)}</select>
      <textarea rows={6} className="border rounded w-full p-2 mb-2 text-sm font-mono" value={f.content} onChange={e=>setF({...f,content:e.target.value})}/>
      <label className="text-sm block mb-2"><input type="checkbox" checked={f.restricted} onChange={e=>setF({...f,restricted:e.target.checked})}/> Restricted (lead only)</label>
      <div className="flex gap-2"><Btn disabled={!f.title||!f.content} onClick={async()=>{await P.call("/api/sources",{method:"POST",body:f});setF({...f,title:"",content:""});P.bump()}}>Import</Btn>
      <Btn className="bg-[#b8860b]" onClick={async()=>{const r=await P.call("/api/extract",{method:"POST"});setMsg(`${r.created} claims extracted, ${r.rejected_uncited} rejected as uncited`);P.bump()}}>Reconstruct &amp; verify</Btn></div>
      {msg&&<p className="text-sm mt-2">{msg}</p>}</Card>
    <Card><h2 className="font-bold mb-2">Your accessible sources ({src.length})</h2>
      <ul className="text-sm space-y-1 mb-4">{src.map(s=><li key={s.id}>• <b>{s.title}</b> <span className="text-slate-500">[{s.kind}]</span>{s.allowed_roles.length===1&&<span className="ml-1 text-xs text-red-700">restricted</span>}</li>)}</ul>
      <h3 className="font-semibold text-sm mb-1">Permission-aware retrieval (pgvector)</h3>
      <div className="flex gap-2"><input className="border rounded flex-1 p-2 text-sm" value={q} onChange={e=>setQ(e.target.value)} placeholder="e.g. hosting decision"/><Btn onClick={async()=>setHits(await P.call("/api/search?q="+encodeURIComponent(q)))}>Search</Btn></div>
      <ul className="text-xs mt-2 space-y-1">{hits.map(h=><li key={h.id}><b>{h.title}</b>: {h.preview}…</li>)}</ul></Card></div>
}

function Review(P){
  const claims=useGet("/api/claims",P)||[],[sel,setSel]=useState(null),[vers,setVers]=useState([]),[ed,setEd]=useState({})
  const c=claims.find(x=>x.id===sel),lead=P.user.role==="lead"
  useEffect(()=>{if(c){setEd({text:c.text,owner:c.owner||""});P.call(`/api/claims/${c.id}/versions`).then(setVers)}},[sel,P.tick])
  const act=async body=>{await P.call(`/api/claims/${c.id}`,{method:"PATCH",body});P.bump()}
  return <div className="grid md:grid-cols-5 gap-4">
    <div className="md:col-span-3 space-y-2">{claims.length===0&&<Card>No claims yet — import sources and press “Reconstruct &amp; verify”.</Card>}
      {claims.map(x=><Card key={x.id} className={"cursor-pointer "+(sel===x.id?"ring-2 ring-[#1f4e79]":"")}><div onClick={()=>setSel(x.id)}>
        <div className="flex gap-2 items-center mb-1"><span className="text-xs uppercase font-bold text-[#1f4e79]">{x.kind.replace("_"," ")}</span><Badge s={x.status}/><span className="text-xs ml-auto">{x.review} · v{x.version}</span></div>
        <p className="text-sm">{x.text}</p><p className="text-xs text-slate-500">Owner: {x.owner||"unknown"} · Source: {x.source_title}</p></div></Card>)}</div>
    <Card className="md:col-span-2 h-fit sticky top-4"><h2 className="font-bold mb-2">Evidence panel</h2>
      {!c?<p className="text-sm text-slate-500">Select a claim to see its source snippet.</p>:<>
        <p className="text-xs text-slate-500">{c.source_title} · {c.source_kind}</p>
        <blockquote className="border-l-4 border-[#e6b800] bg-amber-50 p-2 my-2 text-sm italic">{c.snippet||"Citation redacted — you are not authorised for this source."}</blockquote>
        {lead?<div className="space-y-2">
          <textarea className="border rounded w-full p-2 text-sm" value={ed.text||""} onChange={e=>setEd({...ed,text:e.target.value})}/>
          <input className="border rounded w-full p-2 text-sm" placeholder="Owner" value={ed.owner||""} onChange={e=>setEd({...ed,owner:e.target.value})}/>
          <div className="flex gap-2"><Btn onClick={()=>act(ed)}>Save edit</Btn><Btn className="bg-green-700" onClick={()=>act({review:"approved"})}>Approve</Btn><Btn className="bg-red-700" onClick={()=>act({review:"rejected"})}>Reject</Btn></div></div>
        :<p className="text-xs text-slate-500">Only the reviewer/lead can edit or approve.</p>}
        <h3 className="font-semibold text-sm mt-3">Version history</h3>
        <ul className="text-xs space-y-1">{vers.map(v=><li key={v.id}>v{v.version} · {v.editor} · {new Date(v.at).toLocaleString()}: {v.text}</li>)}</ul></>}</Card></div>
}

function Interview(P){
  const gaps=useGet("/api/gaps",P)||[],[a,setA]=useState({})
  return <Card><h2 className="font-bold mb-1">Targeted gap interview</h2><p className="text-xs text-slate-500 mb-3">Answers become dated, attributable evidence and update the ledger.</p>
    {gaps.length===0&&<p className="text-sm">No open gaps.</p>}
    {gaps.map(g=><div key={g.id} className="mb-3"><p className="text-sm font-medium">{g.question}</p>
      <div className="flex gap-2 mt-1"><input className="border rounded flex-1 p-2 text-sm" value={a[g.id]||""} onChange={e=>setA({...a,[g.id]:e.target.value})} placeholder="Owner name"/>
      <Btn disabled={!a[g.id]} onClick={async()=>{await P.call(`/api/gaps/${g.id}/answer`,{method:"POST",body:{answer:a[g.id]}});P.bump()}}>Submit</Btn></div></div>)}</Card>
}

function Timeline(P){
  const claims=useGet("/api/claims",P)||[]
  return <Card><h2 className="font-bold mb-3">Project timeline</h2><ol className="border-l-2 border-[#1f4e79] ml-2 space-y-3">
    {claims.map(c=><li key={c.id} className="ml-4"><span className="text-xs text-slate-500">{new Date(c.happened_at).toLocaleDateString()}</span>
      <p className="text-sm"><b className="uppercase text-xs text-[#1f4e79]">{c.kind.replace("_"," ")}</b> {c.text} <Badge s={c.status}/></p></li>)}</ol></Card>
}

function Handover(P){
  const d=useGet("/api/handover",P),inc=P.user.role==="incoming"
  if(!d)return null
  return <div className="space-y-3"><Card><h2 className="font-bold">{inc?"Your continuation plan":"Lead view of the handover"}</h2>
    <p className="text-xs text-slate-500">Approved claims only · open questions, risks and next actions first.</p></Card>
    {d.items.length===0&&<Card>Nothing approved yet — a reviewer must approve claims first.</Card>}
    {d.items.map(c=><Card key={c.id}><div className="flex gap-2 items-center"><span className="text-xs uppercase font-bold text-[#1f4e79]">{c.kind.replace("_"," ")}</span><Badge s={c.status}/></div>
      <p className="text-sm mt-1">{c.text}</p><p className="text-xs text-slate-500">Owner: {c.owner||"unknown"} · Cited: {c.source_title} — “{c.snippet||"redacted"}”</p></Card>)}
    {inc&&<Btn onClick={async()=>{await P.call("/api/acknowledge",{method:"POST"});P.bump()}}>Acknowledge handover</Btn>}
    {d.acks.length>0&&<p className="text-sm">Acknowledged by: {d.acks.map(a=>a.user_name).join(", ")}</p>}</div>
}

function Audit(P){
  const rows=useGet("/api/audit",P)||[]
  return <Card><h2 className="font-bold mb-2">Audit trail</h2><ul className="text-xs space-y-1">{rows.map(r=><li key={r.id}>{new Date(r.at).toLocaleString()} · <b>{r.actor}</b> · {r.action} · {r.target}</li>)}</ul></Card>
}
