import { useCallback, useEffect, useRef, useState } from 'react';
import {
  computeLocationStats,
  type LocationStatsResult,
  type PositionSample,
} from '../utils/locationStats';

/** Default collection window aligned with product GPS confidence window (local default; not loaded from API). */
export const DEFAULT_GPS_COLLECT_MS = 15_000;

/** When the default window ends below the required valid sample count, wait until this total elapsed time before failing. */
export const GPS_COLLECT_MAX_TOTAL_MS = 20_000;

export type Coords = {
  latitude: number;
  longitude: number;
  /** Horizontal accuracy in meters (Geolocation API). */
  accuracy: number;
};

export type CollectProgress = {
  elapsedMs: number;
  durationMs: number;
  sampleCount: number;
  validSampleCount: number;
  bestAccuracy: number | null;
  averageAccuracy: number | null;
};

type CollectionResult = {
  stats: LocationStatsResult;
  samples: PositionSample[];
};

type CollectPositionsOptions = {
  durationMs?: number;
  minValidSamples?: number;
};

function geolocationErrorMessage(err: GeolocationPositionError): string {
  if (err.code === err.PERMISSION_DENIED) return 'Permissão de localização negada.';
  if (err.code === err.POSITION_UNAVAILABLE) return 'Localização indisponível.';
  return 'Não foi possível obter o GPS. Tente de novo.';
}

function sampleFromPosition(pos: GeolocationPosition): PositionSample {
  return {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    accuracy: pos.coords.accuracy,
  };
}

function collectProgressSnapshot(
  samples: PositionSample[],
  durationMs: number,
  startedAt: number
): CollectProgress {
  const rawElapsed = Date.now() - startedAt;
  const elapsedMs = Math.min(rawElapsed, GPS_COLLECT_MAX_TOTAL_MS);
  const stats = computeLocationStats(samples);
  return {
    elapsedMs,
    durationMs,
    sampleCount: samples.length,
    validSampleCount: stats?.count ?? 0,
    bestAccuracy: stats?.bestAccuracy ?? null,
    averageAccuracy: stats?.averageAccuracy ?? null,
  };
}

export function useGeolocalizacao() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collectProgress, setCollectProgress] = useState<CollectProgress | null>(null);

  const isMountedRef = useRef(true);
  const activeGetPositionIdRef = useRef(0);
  const activeGetPositionResolveRef = useRef<((value: Coords) => void) | null>(null);
  const activeGetPositionRejectRef = useRef<((reason?: unknown) => void) | null>(null);
  const activeGetPositionSettledRef = useRef(true);
  const collectWatchRef = useRef<number | null>(null);
  const collectIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const collectFinishTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const collectSamplesRef = useRef<PositionSample[]>([]);
  const collectStartedAtRef = useRef<number>(0);
  const activeCollectionIdRef = useRef(0);
  const activeCollectionResolveRef = useRef<((value: CollectionResult) => void) | null>(null);
  const activeCollectionRejectRef = useRef<((reason?: unknown) => void) | null>(null);
  const activeCollectionSettledRef = useRef(true);

  const clearCollectResources = useCallback(() => {
    if (collectWatchRef.current !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(collectWatchRef.current);
    }
    collectWatchRef.current = null;
    if (collectIntervalRef.current !== null) {
      clearInterval(collectIntervalRef.current);
      collectIntervalRef.current = null;
    }
    if (collectFinishTimeoutRef.current !== null) {
      clearTimeout(collectFinishTimeoutRef.current);
      collectFinishTimeoutRef.current = null;
    }
    collectSamplesRef.current = [];
  }, []);

  const finishActiveCollection = useCallback(
    (collectionId: number, finalize: (controls: {
      resolve: (value: CollectionResult) => void;
      reject: (reason?: unknown) => void;
    }) => void) => {
      if (activeCollectionIdRef.current !== collectionId || activeCollectionSettledRef.current) {
        return;
      }

      const resolve = activeCollectionResolveRef.current;
      const reject = activeCollectionRejectRef.current;
      if (!resolve || !reject) return;

      activeCollectionSettledRef.current = true;
      activeCollectionResolveRef.current = null;
      activeCollectionRejectRef.current = null;
      clearCollectResources();

      if (isMountedRef.current) {
        setCollectProgress(null);
        setLoading(false);
      }

      finalize({ resolve, reject });
    },
    [clearCollectResources]
  );

  const cancelActiveCollection = useCallback(
    (message: string) => {
      finishActiveCollection(activeCollectionIdRef.current, ({ reject }) => {
        reject(new Error(message));
      });
    },
    [finishActiveCollection]
  );

  const finishActiveGetPosition = useCallback(
    (
      requestId: number,
      finalize: (controls: {
        resolve: (value: Coords) => void;
        reject: (reason?: unknown) => void;
      }) => void
    ) => {
      if (activeGetPositionIdRef.current !== requestId || activeGetPositionSettledRef.current) {
        return;
      }

      const resolve = activeGetPositionResolveRef.current;
      const reject = activeGetPositionRejectRef.current;
      if (!resolve || !reject) return;

      activeGetPositionSettledRef.current = true;
      activeGetPositionResolveRef.current = null;
      activeGetPositionRejectRef.current = null;

      if (isMountedRef.current && activeCollectionSettledRef.current) {
        setLoading(false);
      }

      finalize({ resolve, reject });
    },
    []
  );

  const cancelActiveGetPosition = useCallback(
    (message: string) => {
      finishActiveGetPosition(activeGetPositionIdRef.current, ({ reject }) => {
        reject(new Error(message));
      });
    },
    [finishActiveGetPosition]
  );

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      cancelActiveGetPosition(
        'Solicitação de localização cancelada porque o componente foi desmontado.'
      );
      cancelActiveCollection('Coleta de localização cancelada porque o componente foi desmontado.');
    };
  }, [cancelActiveCollection, cancelActiveGetPosition]);

  const getPosition = useCallback((): Promise<Coords> => {
    cancelActiveGetPosition('Solicitação de localização cancelada por uma nova solicitação.');
    setLoading(true);
    setError(null);
    return new Promise((resolve, reject) => {
      const requestId = activeGetPositionIdRef.current + 1;
      activeGetPositionIdRef.current = requestId;
      activeGetPositionSettledRef.current = false;
      activeGetPositionResolveRef.current = resolve;
      activeGetPositionRejectRef.current = reject;

      if (!navigator.geolocation) {
        const msg = 'Geolocalização não suportada neste aparelho.';
        finishActiveGetPosition(requestId, ({ reject: rejectActive }) => {
          if (isMountedRef.current) {
            setError(msg);
          }
          rejectActive(new Error(msg));
        });
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          finishActiveGetPosition(requestId, ({ resolve: resolveActive }) => {
            resolveActive({
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
            });
          });
        },
        (err) => {
          const msg = geolocationErrorMessage(err);
          finishActiveGetPosition(requestId, ({ reject: rejectActive }) => {
            if (isMountedRef.current) {
              setError(msg);
            }
            rejectActive(new Error(msg));
          });
        },
        { enableHighAccuracy: true, timeout: 20_000, maximumAge: 0 }
      );
    });
  }, [cancelActiveGetPosition, finishActiveGetPosition]);

  const collectPositions = useCallback(
    ({
      durationMs = DEFAULT_GPS_COLLECT_MS,
      minValidSamples = 1,
    }: CollectPositionsOptions = {}): Promise<CollectionResult> => {
      cancelActiveCollection('Coleta de localização cancelada por uma nova solicitação.');
      setError(null);
      setLoading(true);

      collectSamplesRef.current = [];
      collectStartedAtRef.current = Date.now();
      const collectionId = activeCollectionIdRef.current + 1;
      activeCollectionIdRef.current = collectionId;
      activeCollectionSettledRef.current = false;

      setCollectProgress({
        elapsedMs: 0,
        durationMs,
        sampleCount: 0,
        validSampleCount: 0,
        bestAccuracy: null,
        averageAccuracy: null,
      });

      return new Promise((resolve, reject) => {
        activeCollectionResolveRef.current = resolve;
        activeCollectionRejectRef.current = reject;

        if (!navigator.geolocation) {
          const msg = 'Geolocalização não suportada neste aparelho.';
          if (isMountedRef.current) {
            setError(msg);
          }
          finishActiveCollection(collectionId, ({ reject: rejectActive }) => {
            rejectActive(new Error(msg));
          });
          return;
        }

        const finish = (samples: PositionSample[]) => {
          finishActiveCollection(collectionId, ({ resolve: resolveActive, reject: rejectActive }) => {
            const stats = computeLocationStats(samples);
            if (!stats) {
              const msg =
                'Não obtivemos nenhuma leitura válida do GPS em até 20 segundos. Verifique o sinal e tente de novo.';
              if (isMountedRef.current) {
                setError(msg);
              }
              rejectActive(new Error(msg));
              return;
            }
            if (stats.count < minValidSamples) {
              const msg = `Não foi possível obter ${minValidSamples} leituras válidas do GPS em até 20 segundos. Tente novamente em local aberto.`;
              if (isMountedRef.current) {
                setError(msg);
              }
              rejectActive(new Error(msg));
              return;
            }
            resolveActive({ stats, samples });
          });
        };

        const updateElapsed = () => {
          if (activeCollectionIdRef.current !== collectionId || activeCollectionSettledRef.current) {
            return;
          }
          setCollectProgress(
            collectProgressSnapshot(
              collectSamplesRef.current,
              durationMs,
              collectStartedAtRef.current
            )
          );
        };

        collectIntervalRef.current = setInterval(updateElapsed, 200);
        updateElapsed();

        collectWatchRef.current = navigator.geolocation.watchPosition(
          (pos) => {
            if (activeCollectionIdRef.current !== collectionId || activeCollectionSettledRef.current) {
              return;
            }
            collectSamplesRef.current.push(sampleFromPosition(pos));
            setCollectProgress(
              collectProgressSnapshot(
                collectSamplesRef.current,
                durationMs,
                collectStartedAtRef.current
              )
            );
          },
          (err) => {
            const msg = geolocationErrorMessage(err);
            if (isMountedRef.current) {
              setError(msg);
            }
            finishActiveCollection(collectionId, ({ reject: rejectActive }) => {
              rejectActive(new Error(msg));
            });
          },
          { enableHighAccuracy: true, maximumAge: 0, timeout: 30_000 }
        );

        const scheduleTryFinish = (delayMs: number) => {
          if (collectFinishTimeoutRef.current !== null) {
            clearTimeout(collectFinishTimeoutRef.current);
          }
          collectFinishTimeoutRef.current = setTimeout(() => {
            if (activeCollectionIdRef.current !== collectionId || activeCollectionSettledRef.current) {
              return;
            }
            const samples = [...collectSamplesRef.current];
            const statsNow = computeLocationStats(samples);
            const elapsed = Date.now() - collectStartedAtRef.current;
            if (
              (statsNow?.count ?? 0) < minValidSamples &&
              durationMs === DEFAULT_GPS_COLLECT_MS &&
              elapsed < GPS_COLLECT_MAX_TOTAL_MS
            ) {
              scheduleTryFinish(GPS_COLLECT_MAX_TOTAL_MS - elapsed);
              return;
            }
            finish(samples);
          }, delayMs);
        };

        scheduleTryFinish(durationMs);
      });
    },
    [cancelActiveCollection, finishActiveCollection]
  );

  return {
    getPosition,
    collectPositions,
    collectProgress,
    loading,
    error,
    clearError: () => setError(null),
  };
}
