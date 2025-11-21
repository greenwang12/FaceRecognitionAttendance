import React from "react";
import axios from "axios";

export default function Students(){
  const [list, setList] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState(null);

  React.useEffect(()=>{
    let mounted = true;
    axios.get("/api/v1/students")
      .then(r=> { if(mounted) setList(r.data || []); })
      .catch(e=>{
        if(mounted){
          // surface full server error if available
          const resp = e?.response;
          setErr({
            message: e.message,
            status: resp?.status,
            data: resp?.data
          });
        }
      })
      .finally(()=> { if(mounted) setLoading(false); });
    return ()=> { mounted = false; };
  },[]);

  return (
    <div>
      <div className="h2">Students</div>
      <div className="card">
        {loading && <div className="kv">Loading...</div>}
        {err && (
          <div style={{color:"#c0392b"}}>
            <div><strong>Error:</strong> {err.message}</div>
            <div><strong>HTTP:</strong> {String(err.status || "n/a")}</div>
            <pre style={{whiteSpace:"pre-wrap",marginTop:8}}>{JSON.stringify(err.data, null, 2)}</pre>
          </div>
        )}

        <div style={{marginTop:8}} className="list">
          {list.map(s => (
            <div key={s.id} className="log">
              <div>
                <div style={{fontWeight:700}}>{s.name}</div>
                <div className="kv">{s.roll} · {s.email || "—"}</div>
              </div>
            </div>
          ))}
          {list.length === 0 && !loading && !err && <div className="kv">No students yet</div>}
        </div>
      </div>
    </div>
  );
}
