import { useMutation } from "@tanstack/react-query"
import useCustomToast from "./useCustomToast"

interface WindowStateRequest {
  action: "toggle" | "maximize" | "restore"
}

interface WindowStateResponse {
  status: string
  message: string
}

const toggleWindowState = async (
  action: WindowStateRequest["action"] = "toggle",
): Promise<WindowStateResponse> => {
  const response = await fetch("/api/v1/window", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Unknown error",
    }))
    throw new Error(error.detail || "Failed to change window state")
  }

  return response.json()
}

const useWindowState = () => {
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: toggleWindowState,
    onSuccess: (data) => {
      showSuccessToast(data.message)
    },
    onError: (error: Error) => {
      showErrorToast(error.message)
    },
  })

  const toggleMaximize = () => mutation.mutate("toggle")
  const maximize = () => mutation.mutate("maximize")
  const restore = () => mutation.mutate("restore")

  return {
    toggleMaximize,
    maximize,
    restore,
    isLoading: mutation.isPending,
  }
}

export default useWindowState
