from django.utils import timezone
import uuid
# ==================== HELPER FUNCTIONS ====================

def generate_transaction_id():
    """Generate a unique transaction ID"""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"TXN-{timestamp}-{unique_id}"