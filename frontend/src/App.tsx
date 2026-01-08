import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Jobs from './pages/Jobs'
import Templates from './pages/Templates'
import Logs from './pages/Logs'
import Settings from './pages/Settings'
import Stats from './pages/Stats'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Jobs />} />
          <Route path="templates" element={<Templates />} />
          <Route path="logs" element={<Logs />} />
          <Route path="settings" element={<Settings />} />
          <Route path="stats" element={<Stats />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
