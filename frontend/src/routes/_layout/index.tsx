import { createFileRoute } from "@tanstack/react-router"
import { Maximize2 } from "lucide-react"

import useAuth from "@/hooks/useAuth"
import useWindowState from "@/hooks/useTrayNotification"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - Desktop App",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()
  const { toggleMaximize, isLoading } = useWindowState()

  const handleToggleWindow = () => {
    toggleMaximize()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          Hi, {currentUser?.full_name || currentUser?.email || "User"} 👋
        </h1>
        <p className="text-muted-foreground">
          Welcome back, nice to see you again!!!
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Button
          onClick={handleToggleWindow}
          disabled={isLoading}
          className="gap-2"
        >
          <Maximize2 className="size-4" />
          {isLoading ? "Toggling..." : "Toggle Maximize"}
        </Button>
      </div>
    </div>
  )
}
