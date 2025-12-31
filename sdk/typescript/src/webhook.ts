/**
 * Webhook utilities for YouTube Subtitle API SDK
 */

import crypto from "node:crypto";
import type {
  WebhookPayload,
  Subtitle,
  BatchExtractResponse,
  JobStatus,
} from "./types.js";

/**
 * Verify webhook signature
 *
 * @param payload - The raw webhook payload string
 * @param signature - The signature from the X-Signature header
 * @param secret - Your webhook secret
 * @returns True if the signature is valid
 */
export function verifySignature(
  payload: string,
  signature: string,
  secret: string,
): boolean {
  if (!signature || !secret) {
    return false;
  }

  // Remove 'sha256=' prefix if present
  const signatureBytes = signature.replace(/^sha256=/i, "");

  // Compute HMAC
  const hmac = crypto.createHmac("sha256", secret);
  hmac.update(payload);
  const expectedSignature = hmac.digest("hex");

  // Constant-time comparison to prevent timing attacks
  return crypto.timingSafeEqual(
    Buffer.from(signatureBytes),
    Buffer.from(expectedSignature),
  );
}

/**
 * Parse and validate a webhook payload
 *
 * @param payload - The raw webhook payload (string or already parsed object)
 * @returns The parsed and validated webhook payload
 * @throws ValidationError if the payload is invalid
 */
export function parseWebhook(
  payload: string | Record<string, unknown>,
): WebhookPayload {
  let data: Record<string, unknown>;

  // Parse JSON if string
  if (typeof payload === "string") {
    try {
      data = JSON.parse(payload) as Record<string, unknown>;
    } catch {
      throw new Error("Invalid JSON payload");
    }
  } else {
    data = payload;
  }

  // Validate required fields
  if (!data.event || typeof data.event !== "string") {
    throw new Error("Missing or invalid 'event' field");
  }

  const validEvents = [
    "subtitle.completed",
    "subtitle.failed",
    "batch.completed",
  ] as const;

  if (!validEvents.includes(data.event as any)) {
    throw new Error(`Invalid event type: ${data.event}`);
  }

  if (!data.job_id || typeof data.job_id !== "string") {
    throw new Error("Missing or invalid 'job_id' field");
  }

  if (!data.timestamp) {
    throw new Error("Missing 'timestamp' field");
  }

  if (!data.data || typeof data.data !== "object") {
    throw new Error("Missing or invalid 'data' field");
  }

  return data as WebhookPayload;
}

/**
 * Webhook event handler type
 */
export type WebhookEventHandler = (
  payload: WebhookPayload,
) => void | Promise<void>;

/**
 * Webhook handler configuration
 */
export interface WebhookHandlerConfig {
  /** Webhook secret for signature verification */
  secret: string;
  /** Handler for subtitle completed events */
  onSubtitleCompleted?: (result: Subtitle) => void | Promise<void>;
  /** Handler for subtitle failed events */
  onSubtitleFailed?: (error: {
    job_id: string;
    error: string;
  }) => void | Promise<void>;
  /** Handler for batch completed events */
  onBatchCompleted?: (result: BatchExtractResponse) => void | Promise<void>;
  /** Optional handler for all events */
  onAny?: (payload: WebhookPayload) => void | Promise<void>;
  /** Optional logger */
  logger?: {
    info?: (message: string, ...args: unknown[]) => void;
    error?: (message: string, ...args: unknown[]) => void;
  };
}

/**
 * Create a webhook handler function for use with Express, Fastify, etc.
 *
 * @example
 * ```ts
 * import express from 'express';
 * import { createWebhookHandler } from '@youtube-subtitle-api/sdk/webhook';
 *
 * const app = express();
 * app.use(express.raw({ type: 'application/json' }));
 *
 * const handler = createWebhookHandler({
 *   secret: process.env.WEBHOOK_SECRET!,
 *   onSubtitleCompleted: (result) => {
 *     console.log('Subtitles extracted:', result.video_id);
 *   },
 * });
 *
 * app.post('/webhook', handler);
 * ```
 */
export function createWebhookHandler(
  config: WebhookHandlerConfig,
): (req: {
  body: Buffer;
  headers: Record<string, string>;
}) => Promise<Response> {
  const {
    secret,
    onSubtitleCompleted,
    onSubtitleFailed,
    onBatchCompleted,
    onAny,
    logger = console,
  } = config;

  return async (req): Promise<Response> => {
    try {
      const body = req.body.toString("utf-8");
      const signature = req.headers["x-signature"] || "";

      // Verify signature
      if (!verifySignature(body, signature, secret)) {
        logger.error?.("Invalid webhook signature");
        return new Response("Invalid signature", { status: 401 });
      }

      // Parse payload
      const payload = parseWebhook(body);

      logger.info?.(`Webhook received: ${payload.event}`, {
        job_id: payload.job_id,
      });

      // Call specific handlers
      switch (payload.event) {
        case "subtitle.completed":
          await onSubtitleCompleted?.(payload.data as Subtitle);
          break;
        case "subtitle.failed":
          await onSubtitleFailed?.(
            payload.data as { job_id: string; error: string },
          );
          break;
        case "batch.completed":
          await onBatchCompleted?.(payload.data as BatchExtractResponse);
          break;
      }

      // Call generic handler
      await onAny?.(payload);

      return new Response(JSON.stringify({ received: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    } catch (error) {
      logger.error?.("Webhook handler error", error);
      return new Response(
        JSON.stringify({ error: "Webhook processing failed" }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
  };
}

/**
 * Create a webhook handler for Cloudflare Workers
 *
 * @example
 * ```ts
 * import { createCloudflareWebhookHandler } from '@youtube-subtitle-api/sdk/webhook';
 *
 * export default {
 *   async fetch(request: Request, env: { WEBHOOK_SECRET: string }) {
 *     if (request.url.endsWith('/webhook')) {
 *       const handler = createCloudflareWebhookHandler({
 *         secret: env.WEBHOOK_SECRET,
 *         onSubtitleCompleted: (result) => {
 *           console.log('Subtitles extracted:', result.video_id);
 *         },
 *       });
 *       return handler(request);
 *     }
 *     return new Response('Not found', { status: 404 });
 *   },
 * };
 * ```
 */
export function createCloudflareWebhookHandler(
  config: WebhookHandlerConfig,
): (request: Request) => Promise<Response> {
  const handler = createWebhookHandler(config);

  return async (request: Request): Promise<Response> => {
    const body = await request.arrayBuffer();
    const headers = Object.fromEntries(request.headers.entries());

    return handler({
      body: Buffer.from(body),
      headers,
    });
  };
}
