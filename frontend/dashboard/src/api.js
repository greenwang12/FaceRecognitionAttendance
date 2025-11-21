// src/api.js
import axios from "axios";
const BACK = process.env.REACT_APP_BACKEND || "http://127.0.0.1:8000";
const api = axios.create({ baseURL: BACK, timeout: 10000 });
export default api;
