import React from "react";
import axios from "axios";

export default function Logs(){
  const [logs, setLogs] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState(null);

  React.useEffect(()=>{
    let mounted = true;
    axios.get("/api/v1/attendance/logs")
      .then(r=>{ if(mounted){ setLogs(Array.isArray(r.data) ? r.data : []); } })
      .catch(e=>{
        if(mounted){
          const resp = e?.response;
          setErr({ message: e.message, status: resp?.status, data: resp?.data });
        }
      })
      .finally(()=> mounted && setLoading(false));
    return ()=> { mounted = false; };
  },[]);

  return (
    <div>
      <div className="h2">Attendance Logs</div>
      <div className="card">
        {loading ? <div className="kv">Loading logs…</div> : null}
        {err && (
          <div style={{color:'#c0392b'}}>
            <div><strong>Error:</strong> {err.message}</div>
            <div><strong>HTTP:</strong> {String(err.status || "n/a")}</div>
            <pre style={{whiteSpace:"pre-wrap",marginTop:8}}>{JSON.stringify(err.data, null, 2)}</pre>
          </div>
        )}

        <div style={{marginTop:12}} className="list">
          {logs.map(l => (
            <div className="log" key={l.id}>
              <div>
                <div className="log-name">{l.student_name || l.student_roll}</div>
                <div className="log-time">{new Date(l.entry_time).toLocaleString()}</div>
              </div>
              <div style={{fontWeight:700}}>{l.present ? "Present" : "Absent"}</div>
            </div>
          ))}
          {logs.length === 0 && !loading && !err && <div className="kv">No logs yet — attendance events will appear here.</div>}
        </div>
      </div>
    </div>
  );
}
