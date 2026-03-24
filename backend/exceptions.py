class ServiceAccountConfigError(Exception):
    """Falha ao interpretar GOOGLE_SERVICE_ACCOUNT_JSON (Railway/base64/JSON)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
