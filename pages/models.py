from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class SupportTicket(models.Model):
    """Support ticket model"""
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('answered', 'Answered'),
        ('customer_reply', 'Customer Reply'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    ticket_id = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    department = models.CharField(max_length=50, default='general')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_reply_at = models.DateTimeField(null=True, blank=True)
    last_reply_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_replied')
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Ticket #{self.ticket_id} - {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            # Generate unique ticket ID
            import random
            import string
            timestamp = timezone.now().strftime('%y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.ticket_id = f"TKT-{timestamp}-{random_str}"
        super().save(*args, **kwargs)
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class TicketMessage(models.Model):
    """Individual messages within a ticket"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_staff_reply = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"Message on {self.ticket.ticket_id} by {self.user.username}"


class TicketAttachment(models.Model):
    """File attachments for tickets"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    message = models.ForeignKey(TicketMessage, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(upload_to='ticket_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.file_name


class TicketNote(models.Model):
    """Internal notes for staff (not visible to customer)"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note on {self.ticket.ticket_id}"
    
class Notification(models.Model):
    """User notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'
    
    def __str__(self):
        return f"{self.user.username} - {self.title[:50]}"
    
    @property
    def is_new(self):
        """Check if notification is new (not read)"""
        return not self.read