// src/useWs.js
import { useEffect, useRef } from "react";

export default function useWs(url, onMsg){
  const wsRef = useRef(null);
  useEffect(()=>{
    if(!url) return;
    let alive = true;
    let ws;
    try{ ws = new WebSocket(url); } catch(e){ console.error("ws err", e); return; }
    ws.onopen = ()=> console.log("ws open");
    ws.onmessage = (ev)=> {
      try{
        const j = JSON.parse(ev.data);
        if(onMsg && alive) onMsg(j);
      }catch(e){ console.error("ws parse", e); }
    };
    ws.onerror = (e)=> console.error("ws error", e);
    ws.onclose = ()=> console.log("ws closed");
    wsRef.current = ws;
    return ()=> { alive = false; if(wsRef.current) wsRef.current.close(); };
  }, [url, onMsg]);
  return wsRef;
}
