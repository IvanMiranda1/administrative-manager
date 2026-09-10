class DomainError(Exception):
    """Clase base para errores que representan una violación de invariante."""


class InvalidTransitionError(DomainError):
    """Se intentó una transición de estado que el aggregate no permite."""


class ConfirmedDataOverwriteError(DomainError):
    """
    Se intentó sobreescribir un dato de negocio ya confirmado por un humano
    sin pasar por el flujo de nueva evidencia (snapshot + revisión).
    """


class UnsafeActionError(DomainError):
    """
    Se intentó ejecutar una acción con efecto real (ej. pago) sin
    confirmación humana explícita, sin importar la confianza del dato.
    """
