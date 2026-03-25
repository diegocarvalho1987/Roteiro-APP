import { useEffect, useState } from 'react';

const STORAGE_KEY = 'roteiro.warmLocation.v1';
const WARM_LOCATION_TTL_MS = 8_000;
const FUTURE_TIMESTAMP_SKEW_MS = 5_000;
const RECENCY_OVERRIDE_MS = 20_000;
const MOVE_OVERRIDE_METERS = 75;

export type WarmLocationReading = {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
};

function haversineMeters(a: WarmLocationReading, b: WarmLocationReading): number {
  const toRad = (degrees: number) => (degrees * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLng = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
  return 6371_000 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

function isFreshReading(reading: WarmLocationReading, now = Date.now()): boolean {
  if (!Number.isFinite(reading.timestamp)) return false;
  if (reading.timestamp > now + FUTURE_TIMESTAMP_SKEW_MS) return false;
  return now - reading.timestamp <= WARM_LOCATION_TTL_MS;
}

function parseStored(raw: string | null): WarmLocationReading | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as unknown;
    if (!v || typeof v !== 'object') return null;
    const o = v as Record<string, unknown>;
    const latitude = o.latitude;
    const longitude = o.longitude;
    const accuracy = o.accuracy;
    const timestamp = o.timestamp;
    if (
      typeof latitude !== 'number' ||
      typeof longitude !== 'number' ||
      typeof accuracy !== 'number' ||
      typeof timestamp !== 'number' ||
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      !Number.isFinite(accuracy) ||
      !Number.isFinite(timestamp) ||
      accuracy < 0
    ) {
      return null;
    }
    return { latitude, longitude, accuracy, timestamp };
  } catch {
    return null;
  }
}

function clearStoredWarmLocation() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function readStoredWarmLocation(): {
  reading: WarmLocationReading | null;
  shouldClear: boolean;
} {
  try {
    const stored = parseStored(sessionStorage.getItem(STORAGE_KEY));
    if (!stored || !isFreshReading(stored)) {
      return { reading: null, shouldClear: stored !== null };
    }
    return { reading: stored, shouldClear: false };
  } catch {
    return { reading: null, shouldClear: true };
  }
}

export function readWarmLocationSnapshot(): WarmLocationReading | null {
  if (typeof sessionStorage === 'undefined') return null;
  const { reading, shouldClear } = readStoredWarmLocation();
  if (shouldClear) {
    clearStoredWarmLocation();
  }
  return reading;
}

export type UseWarmLocationOptions = {
  /** When false, skips reading initial state from sessionStorage. Default true. */
  restoreFromSession?: boolean;
};

/**
 * Keeps a watch on geolocation while the document is visible and retains a useful
 * recent fix in memory. Prefer better accuracy for short intervals, but let newer
 * readings replace older ones so the cache does not cling to a previous stop.
 */
export function useWarmLocation(options?: UseWarmLocationOptions) {
  const restore = options?.restoreFromSession !== false;
  const [initialStored] = useState(() =>
    restore && typeof sessionStorage !== 'undefined'
      ? readStoredWarmLocation()
      : { reading: null, shouldClear: false }
  );

  const [bestReading, setBestReading] = useState<WarmLocationReading | null>(() => {
    return initialStored.reading;
  });

  useEffect(() => {
    if (!initialStored.shouldClear) return;
    clearStoredWarmLocation();
  }, [initialStored.shouldClear]);

  useEffect(() => {
    if (!navigator.geolocation) return;

    let watchId: number | undefined;

    const persist = (reading: WarmLocationReading) => {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(reading));
      } catch {
        /* ignore quota / private mode */
      }
    };

    const considerUpdate = (
      latitude: number,
      longitude: number,
      accuracy: number,
      timestamp: number
    ) => {
      if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        !Number.isFinite(accuracy) ||
        accuracy < 0 ||
        !Number.isFinite(timestamp)
      ) {
        return;
      }
      const next: WarmLocationReading = {
        latitude,
        longitude,
        accuracy,
        timestamp,
      };
      setBestReading((prev) => {
        if (!prev || !isFreshReading(prev, next.timestamp)) {
          persist(next);
          return next;
        }

        const movedMeters = haversineMeters(prev, next);
        if (movedMeters >= MOVE_OVERRIDE_METERS) {
          persist(next);
          return next;
        }

        if (
          next.timestamp - prev.timestamp < RECENCY_OVERRIDE_MS &&
          prev.accuracy <= next.accuracy
        ) {
          return prev;
        }
        persist(next);
        return next;
      });
    };

    const startWatch = () => {
      if (watchId !== undefined) return;
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          considerUpdate(
            pos.coords.latitude,
            pos.coords.longitude,
            pos.coords.accuracy,
            Number.isFinite(pos.timestamp) ? pos.timestamp : Date.now()
          );
        },
        () => {
          /* permission or hardware errors: fail silently; callers use useGeolocalizacao for UX */
        },
        { enableHighAccuracy: true, maximumAge: 60_000, timeout: 30_000 }
      );
    };

    const stopWatch = () => {
      if (watchId === undefined) return;
      navigator.geolocation.clearWatch(watchId);
      watchId = undefined;
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') startWatch();
      else stopWatch();
    };

    onVisibility();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      stopWatch();
    };
  }, []);

  useEffect(() => {
    if (!bestReading) return;

    const remainingMs = WARM_LOCATION_TTL_MS - (Date.now() - bestReading.timestamp);
    if (remainingMs <= 0) {
      setBestReading(null);
      clearStoredWarmLocation();
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setBestReading((current) => {
        if (!current || current.timestamp !== bestReading.timestamp) {
          return current;
        }
        clearStoredWarmLocation();
        return null;
      });
    }, remainingMs);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [bestReading]);

  const clearBestReading = () => {
    setBestReading(null);
    clearStoredWarmLocation();
  };

  return { bestReading, clearBestReading };
}
