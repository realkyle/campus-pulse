import { getAccessToken } from "@auth0/nextjs-auth0";
import { API_URL } from "@/lib/config";

/**
 * fetch() to the backend as the signed-in user: attaches the Auth0 access token
 * (from this app's /auth/access-token route) as a Bearer token. The backend
 * identifies the user only from this token (api/recommendations.md).
 * Throws if there's no session or the token can't be obtained.
 */
export async function fetchAsUser(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getAccessToken();
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${token}` },
  });
}
