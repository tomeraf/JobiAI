import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Jobs from './pages/Jobs'
import Templates from './pages/Templates'
import Logs from './pages/Logs'
import Settings from './pages/Settings'
import Stats from './pages/Stats'
import { systemApi } from './api/client'

function App() {
  useEffect(() => {
    // Send heartbeat every 15 seconds to keep server alive
    const heartbeatInterval = setInterval(() => {
      systemApi.heartbeat()
    }, 15000)

    // Send initial heartbeat immediately
    systemApi.heartbeat()

    // Shutdown server when tab/window closes
    const handleUnload = () => {
      systemApi.shutdown()
    }

    window.addEventListener('beforeunload', handleUnload)

    return () => {
      clearInterval(heartbeatInterval)
      window.removeEventListener('beforeunload', handleUnload)
    }
  }, [])

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
