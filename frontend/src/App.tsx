import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import TasksPage from './pages/TasksPage'
import RecitePage from './pages/RecitePage'

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/tasks',
    element: <TasksPage />,
  },
  {
    path: '/recite/:taskId',
    element: <RecitePage />,
  },
  {
    path: '/',
    element: <LoginPage />,
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App
