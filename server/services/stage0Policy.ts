export const STAGE0_SUPPORTED_PROVIDERS = ['groq', 'gemini', 'local'] as const;

export const STAGE0_DEFAULT_MODELS: Record<Stage0Provider, string> = {
  groq: 'openai/gpt-oss-120b',
  gemini: 'gemini-3.5-flash-lite',
  local: 'qwen2.5:7b-instruct-q4_K_M',
};

export type Stage0Provider = (typeof STAGE0_SUPPORTED_PROVIDERS)[number];

export interface Stage0EvidencePolicy {
  provider_order: Stage0Provider[];
  models: Partial<Record<Stage0Provider, string>>;
  local_only: boolean;
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function cleanProviderOrder(value: unknown): Stage0Provider[] {
  const values = Array.isArray(value) ? value : [];
  const result: Stage0Provider[] = [];
  for (const raw of values) {
    const provider = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
    if (
      (STAGE0_SUPPORTED_PROVIDERS as readonly string[]).includes(provider)
      && !result.includes(provider as Stage0Provider)
    ) {
      result.push(provider as Stage0Provider);
    }
  }
  return result;
}

// Implements FR-279 and AC-368: keep provider/model normalization identical to Python.
export function normalizeStage0EvidencePolicy(settings: unknown): Stage0EvidencePolicy {
  const root = recordValue(settings);
  const config = recordValue(root.stage0_evidence_classification);
  const localOnly = config.local_only === true
    || ['1', 'true', 'yes', 'on'].includes((process.env.LOCAL_ONLY_MODE ?? '').toLowerCase());
  const configured = cleanProviderOrder(config.provider_order);
  const providerOrder: Stage0Provider[] = localOnly
    ? ['local' as Stage0Provider]
    : configured.length
      ? configured
      : ['groq', 'gemini'];
  const configuredModels = recordValue(config.models);
  const models: Partial<Record<Stage0Provider, string>> = {};
  for (const provider of providerOrder) {
    const model = configuredModels[provider];
    models[provider] = typeof model === 'string' && model.trim()
      ? model.trim()
      : STAGE0_DEFAULT_MODELS[provider];
  }
  return {
    provider_order: providerOrder,
    models,
    local_only: localOnly,
  };
}
