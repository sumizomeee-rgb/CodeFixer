import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './product.css'
import './simplify.css'
import './ai-picker.css'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
