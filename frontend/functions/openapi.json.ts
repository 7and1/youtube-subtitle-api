import { optionsResponse, proxyToBackend, requireBackendBase } from "./_proxy";

export const onRequest: PagesFunction<{
  BACKEND_BASE_URL: string;
  BACKEND_API_KEY?: string;
}> = async ({ request, env }) => {
  const backendBase = requireBackendBase(env);
  if (request.method.toUpperCase() === "OPTIONS") return optionsResponse();
  const url = `${backendBase}/openapi.json${new URL(request.url).search}`;
  return proxyToBackend(request, env, url);
};
