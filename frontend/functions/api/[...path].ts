import { optionsResponse, proxyToBackend, requireBackendBase } from "../_proxy";

export const onRequest: PagesFunction<{
  BACKEND_BASE_URL: string;
  BACKEND_API_KEY?: string;
}> = async ({ request, params, env }) => {
  const backendBase = requireBackendBase(env);

  if (request.method.toUpperCase() === "OPTIONS") return optionsResponse();

  const path = Array.isArray(params.path)
    ? params.path.join("/")
    : String(params.path || "");
  const search = new URL(request.url).search;
  const url = `${backendBase}/api/${path}${search}`;
  return proxyToBackend(request, env, url);
};
