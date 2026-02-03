import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_access_token_api_v1_login_access_token_post as AccessToken,
  LoginService,
  type ReadUserMeApiV1UsersMeGetResponse as UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  // Always fetch user - backend returns default user when auth is disabled
  const { data: user } = useQuery<UserPublic | undefined, Error>({
    queryKey: ["currentUser"],
    queryFn: () => UsersService.readUserMeApiV1UsersMeGet(),
    retry: false,
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUserApiV1UsersSignupPost({ requestBody: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    const response =
      await LoginService.accessTokenApiV1LoginAccessTokenPost({
        formData: data,
      })
    localStorage.setItem("access_token", response.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    queryClient.invalidateQueries({ queryKey: ["currentUser"] })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
    isLoggedIn,
  }
}

export { isLoggedIn }
export default useAuth
