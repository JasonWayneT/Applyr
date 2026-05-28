import { WebWorkerMLCEngineHandler } from '@mlc-ai/web-llm';

// Hook up the worker handler to provide the MLC engine over postMessage
const handler = new WebWorkerMLCEngineHandler();
self.onmessage = (msg: MessageEvent) => {
  handler.onmessage(msg);
};
