const AUTH_ERROR_MESSAGES: Record<string, string> = {
  AccessDenied: "Discord did not allow the sign-in request. Please try again.",
  AccountDeactivated:
    "Your account has been deactivated. Contact an administrator if you need access restored.",
  CallbackRouteError:
    "Discord sign-in could not be completed. Please try again in a moment.",
  Configuration: "Authentication is temporarily unavailable. Please try again shortly.",
  Default: "Authentication failed. Please try signing in again.",
  OAuthAccountNotLinked:
    "This Discord account could not be linked to the existing session. Sign out and try again.",
  OAuthCallback:
    "Discord returned an invalid sign-in response. Please try again.",
  OAuthSignin: "Discord sign-in could not be started. Please try again.",
  SessionExpired: "Your session is no longer linked to your study profile. Sign in with Discord again.",
  SessionRequired: "Please sign in to continue.",
  Verification: "The sign-in verification request expired. Please try again.",
};

export function getAuthErrorMessage(errorCode?: string | null): string | null {
  if (!errorCode) {
    return null;
  }

  return AUTH_ERROR_MESSAGES[errorCode] ?? AUTH_ERROR_MESSAGES.Default;
}
