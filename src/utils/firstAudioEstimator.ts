export const MAX_FIRST_AUDIO_SAMPLES = 20;
export const MIN_SAMPLES_FOR_ESTIMATE = 3;

export type FirstAudioContext = {
  backend: string;
  voice: string;
  firstSegmentChars: number;
};

export type FirstAudioSample = FirstAudioContext & {
  durationMs: number;
};

type SegmentSizeBucket = "short" | "medium" | "long";

function segmentSizeBucket(characterCount: number): SegmentSizeBucket {
  if (characterCount <= 40) return "short";
  if (characterCount <= 90) return "medium";
  return "long";
}

function isComparable(sample: FirstAudioSample, context: FirstAudioContext): boolean {
  return sample.backend === context.backend
    && sample.voice === context.voice
    && segmentSizeBucket(sample.firstSegmentChars) === segmentSizeBucket(context.firstSegmentChars);
}

export function recordFirstAudioSample(
  history: readonly FirstAudioSample[],
  durationMs: number,
  context: FirstAudioContext,
  maxSamples = MAX_FIRST_AUDIO_SAMPLES,
): FirstAudioSample[] {
  if (
    !Number.isFinite(durationMs)
    || durationMs <= 0
    || maxSamples <= 0
    || !context.backend
    || !context.voice
    || !Number.isFinite(context.firstSegmentChars)
    || context.firstSegmentChars <= 0
  ) {
    return [...history].slice(-Math.max(0, maxSamples));
  }

  // Ignore extreme process stalls. They are not useful predictions for a normal
  // request and would make the small status indicator look broken for weeks.
  const sample: FirstAudioSample = {
    ...context,
    firstSegmentChars: Math.round(context.firstSegmentChars),
    durationMs: Math.min(Math.round(durationMs), 30_000),
  };
  return [...history, sample].slice(-maxSamples);
}

export function estimateFirstAudioMs(
  history: readonly FirstAudioSample[],
  context: FirstAudioContext | null,
): number | null {
  if (context === null) return null;
  const samples = history
    .filter((sample) => isComparable(sample, context))
    .map((sample) => sample.durationMs)
    .filter((durationMs) => Number.isFinite(durationMs) && durationMs > 0)
    .sort((a, b) => a - b);
  if (samples.length < MIN_SAMPLES_FOR_ESTIMATE) return null;

  const middle = Math.floor(samples.length / 2);
  const median = samples.length % 2 === 0
    ? (samples[middle - 1] + samples[middle]) / 2
    : samples[middle];
  return Math.round(median);
}

export function estimatedGenerationProgress(
  elapsedMs: number,
  estimateMs: number | null,
): number | null {
  if (estimateMs === null || estimateMs <= 0) return null;
  const safeElapsed = Math.max(0, elapsedMs);
  // A time-based indicator must never claim completion before audio actually
  // starts. It fills linearly to 90%, then waits truthfully for the real event.
  return Math.min(0.9, safeElapsed / estimateMs * 0.9);
}

export function estimatedRemainingLabel(
  elapsedMs: number,
  estimateMs: number | null,
): string | null {
  if (estimateMs === null || estimateMs <= 0) return null;
  const remainingMs = estimateMs - Math.max(0, elapsedMs);
  if (remainingMs <= 0) return "almost ready";
  // Half-second steps avoid implying precision the rolling median cannot offer.
  const roundedSeconds = Math.max(0.5, Math.ceil(remainingMs / 500) * 0.5);
  return `~${roundedSeconds.toFixed(1)}s`;
}
