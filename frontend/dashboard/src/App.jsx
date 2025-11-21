import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dash from "./pages/Dashboard";
import Students from "./pages/Students";
import FaceReg from "./pages/FaceReg";
import Live from "./pages/Live";
import Logs from "./pages/Logs";

export default function App(){
  return (
    <BrowserRouter>
      <div className="app-wrap">
        <aside className="app-aside">
          <div style={{padding:"10px 8px"}}>
            <div className="brand">Attendance</div>
            <nav className="nav" style={{marginTop:12}}>
              <NavLink to="/" end className={({isActive})=> isActive ? "active" : ""}>Dashboard</NavLink>
              <NavLink to="/students" className={({isActive})=> isActive ? "active" : ""}>Students</NavLink>
              <NavLink to="/face-register" className={({isActive})=> isActive ? "active" : ""}>Register Face</NavLink>
              <NavLink to="/live" className={({isActive})=> isActive ? "active" : ""}>Live Monitor</NavLink>
              <NavLink to="/logs" className={({isActive})=> isActive ? "active" : ""}>Attendance Logs</NavLink>
            </nav>
          </div>
        </aside>

        <main className="main-area">
          <div className="page">
            <Routes>
              <Route path="/" element={<Dash/>} />
              <Route path="/students" element={<Students/>} />
              <Route path="/face-register" element={<FaceReg/>} />
              <Route path="/live" element={<Live/>} />
              <Route path="/logs" element={<Logs/>} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}
