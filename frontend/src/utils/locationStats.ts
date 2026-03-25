export type PositionSample = {
  latitude: number;
  longitude: number;
  accuracy: number;
};

export type LocationStatsResult = {
  averageLatitude: number;
  averageLongitude: number;
  averageAccuracy: number;
  /** Smallest accuracy value among samples (meters); lower is better. */
  bestAccuracy: number;
  count: number;
};

function isValidSample(s: PositionSample): boolean {
  return (
    Number.isFinite(s.latitude) &&
    Number.isFinite(s.longitude) &&
    Number.isFinite(s.accuracy) &&
    s.accuracy >= 0
  );
}

/**
 * Aggregates GPS samples collected over a window.
 * Returns null when there are no valid samples.
 */
export function computeLocationStats(samples: PositionSample[]): LocationStatsResult | null {
  const valid = samples.filter(isValidSample);
  if (valid.length === 0) return null;

  let sumLat = 0;
  let sumLng = 0;
  let sumAcc = 0;
  let bestAccuracy = Infinity;

  for (const s of valid) {
    sumLat += s.latitude;
    sumLng += s.longitude;
    sumAcc += s.accuracy;
    if (s.accuracy < bestAccuracy) bestAccuracy = s.accuracy;
  }

  const n = valid.length;
  return {
    averageLatitude: sumLat / n,
    averageLongitude: sumLng / n,
    averageAccuracy: sumAcc / n,
    bestAccuracy,
    count: n,
  };
}
