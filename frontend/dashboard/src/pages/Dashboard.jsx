import React from "react";
import axios from "axios";

export default function Dashboard(){
  const [stats, setStats] = React.useState({students:0,todays:0});
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState(null);

  React.useEffect(()=>{
    let mounted = true;
    axios.get('/api/v1/dashboard/summary')
      .then(r=>{
        if(mounted && r && r.data){
          setStats(Object.assign({students:0,todays:0}, r.data));
        }
      })
      .catch(e=>{
        console.warn("Dashboard summary not available:", e.message || e);
        if(mounted) setErr(e.message || "Not available");
      })
      .finally(()=> mounted && setLoading(false));
    return ()=> mounted = false;
  },[]);

  return (
    <div>
      <div className="h1">Attendance Dashboard</div>
      <div className="kv">Overview</div>

      {loading ? (
        <div className="card">Loading…</div>
      ) : err ? (
        <div className="card" style={{color:"#c0392b"}}>Error: {err}</div>
      ) : (
        <div style={{display:"flex",gap:14,marginTop:12}}>
          <div className="card" style={{flex:1}}>
            <div style={{fontSize:28,fontWeight:800}}>{stats.students}</div>
            <div className="kv">Total students</div>
          </div>
          <div className="card" style={{flex:1}}>
            <div style={{fontSize:28,fontWeight:800}}>{stats.todays}</div>
            <div className="kv">Today present</div>
          </div>
        </div>
      )}
    </div>
  );
}
