import { optionsResponse, proxyToBackend, requireBackendBase } from "../_proxy";

export const onRequest: PagesFunction<{
  BACKEND_BASE_URL: string;
  BACKEND_API_KEY?: string;
}> = async ({ request, params, env }) => {
  const backendBase = requireBackendBase(env);
  if (request.method.toUpperCase() === "OPTIONS") return optionsResponse();

  const rest = Array.isArray(params.path)
    ? params.path.join("/")
    : String(params.path || "");
  const suffix = rest ? `/${rest}` : "";
  const url = `${backendBase}/docs${suffix}${new URL(request.url).search}`;
  return proxyToBackend(request, env, url);
};
