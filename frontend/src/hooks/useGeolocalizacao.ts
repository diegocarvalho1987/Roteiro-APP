import { useCallback, useState } from 'react';

export type Coords = { latitude: number; longitude: number };

export function useGeolocalizacao() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getPosition = useCallback((): Promise<Coords> => {
    setLoading(true);
    setError(null);
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        setLoading(false);
        const msg = 'Geolocalização não suportada neste aparelho.';
        setError(msg);
        reject(new Error(msg));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLoading(false);
          resolve({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
          });
        },
        (err) => {
          setLoading(false);
          const msg =
            err.code === err.PERMISSION_DENIED
              ? 'Permissão de localização negada.'
              : err.code === err.POSITION_UNAVAILABLE
                ? 'Localização indisponível.'
                : 'Não foi possível obter o GPS. Tente de novo.';
          setError(msg);
          reject(new Error(msg));
        },
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
      );
    });
  }, []);

  return { getPosition, loading, error, clearError: () => setError(null) };
}
