from enum import Enum


class ItemStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"  # baja confianza: requiere que un humano confirme
    PENDING = "pending"            # accionable, ya confirmado o de alta confianza
    WAITING = "waiting"            # marcado manualmente: depende de otra persona
    COMPLETED = "completed"
    CANCELLED = "cancelled"
