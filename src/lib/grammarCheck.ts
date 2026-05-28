/**
 * Implements WebGPU Browser-Side Inference for Grammar checks.
 * Uses @mlc-ai/web-llm to run a small model locally in the browser,
 * offloading grammar/spell checks from the server and ensuring privacy.
 */

let engine: any = null;

export async function initGrammarChecker(progressCallback?: (info: any) => void) {
  if (engine) return engine;
  
  try {
    // Dynamic import to avoid breaking SSR or initial bundle size
    const { CreateWebWorkerMLCEngine } = await import('@mlc-ai/web-llm');
    
    engine = await CreateWebWorkerMLCEngine(
      new Worker(new URL('./grammar-worker.ts', import.meta.url), { type: 'module' }),
      'Llama-3-8B-Instruct-q4f32_1-MLC',
      { initProgressCallback: progressCallback }
    );
    return engine;
  } catch (err) {
    console.error("Failed to initialize WebGPU grammar checker:", err);
    return null;
  }
}

export async function checkGrammarLocal(text: string): Promise<string> {
  if (!engine) {
    await initGrammarChecker();
  }
  
  if (!engine) {
    console.warn("WebGPU not available, falling back to server...");
    return text; // Fallback
  }
  
  const prompt = `Fix all grammar and spelling errors in the following text. Return ONLY the corrected text.\n\n${text}`;
  
  try {
    const reply = await engine.chat.completions.create({
      messages: [{ role: "user", content: prompt }],
      temperature: 0.1,
    });
    return reply.choices[0].message.content || text;
  } catch (e) {
    console.error("Grammar check failed:", e);
    return text;
  }
}
