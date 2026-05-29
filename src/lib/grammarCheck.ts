/**
 * WebGPU grammar analysis — highlight-only, no document rewrite (CR-021).
 */

export interface GrammarIssue {
  message: string;
  severity: 'info' | 'warn';
}

let engine: unknown = null;

export async function initGrammarChecker(progressCallback?: (info: unknown) => void) {
  if (engine) return engine;

  try {
    const { CreateWebWorkerMLCEngine } = await import('@mlc-ai/web-llm');

    engine = await CreateWebWorkerMLCEngine(
      new Worker(new URL('./grammar-worker.ts', import.meta.url), { type: 'module' }),
      'Llama-3-8B-Instruct-q4f32_1-MLC',
      { initProgressCallback: progressCallback },
    );
    return engine;
  } catch (err) {
    console.error('Failed to initialize WebGPU grammar checker:', err);
    return null;
  }
}

/** Returns issues only — never mutates resume/cover facts. */
export async function analyzeGrammarIssues(text: string): Promise<GrammarIssue[]> {
  if (!engine) {
    await initGrammarChecker();
  }
  if (!engine) {
    return [];
  }

  const prompt = `List grammar or spelling issues in the text below as JSON array of strings.
Do NOT rewrite the text. Do NOT suggest new facts or numbers.
Output ONLY: {"issues":["issue 1","issue 2"]}

${text.slice(0, 2500)}`;

  try {
    const eng = engine as {
      chat: { completions: { create: (opts: unknown) => Promise<{ choices: { message: { content?: string } }[] }> } };
    };
    const reply = await eng.chat.completions.create({
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.0,
    });
    const raw = reply.choices[0]?.message?.content || '{"issues":[]}';
    const parsed = JSON.parse(raw.replace(/```json|```/g, '').trim()) as { issues?: string[] };
    return (parsed.issues || []).map((message) => ({ message, severity: 'warn' as const }));
  } catch (e) {
    console.error('Grammar analysis failed:', e);
    return [];
  }
}

/** @deprecated Use analyzeGrammarIssues — returns original text unchanged. */
export async function checkGrammarLocal(text: string): Promise<string> {
  const issues = await analyzeGrammarIssues(text);
  if (issues.length) {
    console.info('[Grammar]', issues.map((i) => i.message).join('; '));
  }
  return text;
}
