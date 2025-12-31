/**
 * Webhook Server Example
 *
 * This example demonstrates how to set up a webhook server
 * to receive subtitle extraction completion notifications.
 */

import { createWebhookHandler } from "../src/webhook.js";
import { serve } from "https://deno.land/std@0.200.0/http/server.ts";

// Your webhook secret (configure this in your API settings)
const WEBHOOK_SECRET = Deno.env.get("WEBHOOK_SECRET") || "your-webhook-secret";

// Create the webhook handler
const webhookHandler = createWebhookHandler({
  secret: WEBHOOK_SECRET,
  onSubtitleCompleted: (result) => {
    console.log("Subtitle completed:", {
      video_id: result.video_id,
      title: result.title,
      subtitle_count: result.subtitle_count,
    });
  },
  onSubtitleFailed: (error) => {
    console.error("Subtitle failed:", {
      job_id: error.job_id,
      error: error.error,
    });
  },
  onBatchCompleted: (result) => {
    console.log("Batch completed:", {
      total: result.total,
      successful: result.successful,
      failed: result.failed,
    });
  },
  onAny: (payload) => {
    console.log("Webhook received:", payload.event, payload.job_id);
  },
  logger: console,
});

// Start the server
async function handleRequest(req: Request): Promise<Response> {
  const url = new URL(req.url);

  if (url.pathname === "/webhook") {
    // Read the raw body
    const body = await req.arrayBuffer();
    const headers = Object.fromEntries(req.headers.entries());

    return webhookHandler({ body: Buffer.from(body), headers });
  }

  return new Response("Webhook server running. POST to /webhook", {
    status: 200,
    headers: { "Content-Type": "text/plain" },
  });
}

console.log("Webhook server listening on http://localhost:3000");
console.log("Endpoints:");
console.log("  POST /webhook - Receive webhook events");

await serve(handleRequest, { port: 3000 });
