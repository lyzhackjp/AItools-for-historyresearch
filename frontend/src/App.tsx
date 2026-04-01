import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Layout, theme } from 'antd'
import MainLayout from './components/layout/MainLayout'
import HomePage from './pages/Home'
import PaperPolishPage from './pages/PaperPolish'
import OcrProcessPage from './pages/OcrProcess'
import EntityRecognitionPage from './pages/EntityRecognition'
import NoteGeneratorPage from './pages/NoteGenerator'
import ResearchAssistantPage from './pages/ResearchAssistant'
import SettingsPage from './pages/Settings'
import PromptEditorPage from './pages/PromptEditor'
import { useApiStore } from './stores/useApiStore'
import './index.css'

const { Content } = Layout

function App() {
  const [isLoading, setIsLoading] = useState(true)
  const { loadFromStorage } = useApiStore()
  const { token } = theme.useToken()

  useEffect(() => {
    loadFromStorage()
    setIsLoading(false)
  }, [loadFromStorage])

  if (isLoading) {
    return null
  }

  return (
    <BrowserRouter>
      <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
        <MainLayout>
          <Content style={{ padding: '24px', margin: 0, minHeight: 280 }}>
            <Routes>
              <Route path="/" element={<Navigate to="/home" replace />} />
              <Route path="/home" element={<HomePage />} />
              <Route path="/paper-polish" element={<PaperPolishPage />} />
              <Route path="/ocr-process" element={<OcrProcessPage />} />
              <Route path="/entity-recognition" element={<EntityRecognitionPage />} />
              <Route path="/note-generator" element={<NoteGeneratorPage />} />
              <Route path="/research-assistant" element={<ResearchAssistantPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/prompt-editor" element={<PromptEditorPage />} />
            </Routes>
          </Content>
        </MainLayout>
      </Layout>
    </BrowserRouter>
  )
}

export default App
