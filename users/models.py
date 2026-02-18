from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

# ==================== USER MODELS ====================
class UserManager(BaseUserManager):
    """Custom user manager for handling both regular users and admins"""
    
    def create_user(self, username, email, password=None, **extra_fields):
        """Create and return a regular user"""
        if not email:
            raise ValueError('Email is required')
        if not username:
            raise ValueError('Username is required')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        """Create and return a superuser (full admin)"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('status', 'active')
        extra_fields.setdefault('can_create_child_panels', True) 
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(username, email, password, **extra_fields)
    
    def create_admin(self, username, email, password=None, **extra_fields):
        """Create and return an admin user (not superuser)"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('status', 'active')
        extra_fields.setdefault('can_create_child_panels', True) 
        
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    """Extended user model with SMM-specific fields"""
    username = models.CharField(unique=True,max_length=15)
    email = models.EmailField(unique=True)
    phone = models.CharField(null=True,blank=True, max_length=11 )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_orders = models.IntegerField(default=0)
    can_create_child_panels = models.BooleanField(default=False)
    class UserStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        BANNED = 'banned', 'Banned'
    
    status = models.CharField(
        max_length=20, 
        choices=UserStatus.choices, 
        default=UserStatus.ACTIVE
    )
    
    class UserRole(models.TextChoices):
        USER = 'user', 'User'
        ADMIN = 'admin', 'Admin'
        RESELLER = 'reseller', 'Reseller'
    
    role = models.CharField(
        max_length=20, 
        choices=UserRole.choices, 
        default=UserRole.USER
    )
    
    email_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='3600')
    api_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    api_secret = models.CharField(max_length=64, null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    order_completed_notify = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def add_balance(self, amount):
        """Add funds to user balance"""
        self.balance += amount
        self.save()
    
    def deduct_balance(self, amount):
        """Deduct funds from user balance"""
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False
#==================== PAYMENTGATEWAY MODELS ===================
class PaymentGateway(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    public_key = models.CharField(max_length=255, blank=True)
    secret_key = models.CharField(max_length=255, blank=True)
    api_endpoint = models.URLField(blank=True)
    
    commission_enabled = models.BooleanField(default=False)
    commission_fixed = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    instructions = models.TextField(blank=True)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
# ==================== SERVICE MODELS ====================

class ServiceCategory(models.Model):
    """Categories for SMM services (Instagram, TikTok, etc.)"""
    
    class Platform(models.TextChoices):
        INSTAGRAM = 'instagram', 'Instagram'
        TIKTOK = 'tiktok', 'TikTok'
        TWITTER = 'twitter', 'Twitter'
        YOUTUBE = 'youtube', 'YouTube'
        FACEBOOK = 'facebook', 'Facebook'
    
    name = models.CharField(max_length=100)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    display_order = models.IntegerField(default=0)
    icon_class = models.CharField(max_length=100, help_text="Font Awesome icon class", 
                                  default="fab fa-instagram")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'service_categories'
        ordering = ['display_order', 'name']
        verbose_name_plural = "Service categories"
    
    def __str__(self):
        return f"{self.get_platform_display()} - {self.name}"


class Service(models.Model):
    """Individual SMM services available for purchase"""
    
    class ServiceType(models.TextChoices):
        FOLLOWERS = 'followers', 'Followers'
        LIKES = 'likes', 'Likes'
        VIEWS = 'views', 'Views'
        COMMENTS = 'comments', 'Comments'
        SHARES = 'shares', 'Shares'
        RETWEETS = 'retweets', 'Retweets'
        SUBSCRIBERS = 'subscribers', 'Subscribers'
        SAVES = 'saves', 'Saves'
    
    class Speed(models.TextChoices):
        SLOW = 'slow', 'Slow'
        MEDIUM = 'medium', 'Medium'
        FAST = 'fast', 'Fast'
        INSTANT = 'instant', 'Instant'
    
    class Quality(models.TextChoices):
        HIGH = 'high', 'High (Real users)'
        MEDIUM = 'medium', 'Medium (Mix)'
        LOW = 'low', 'Low (Bot)'
    
    # Basic info
    category = models.ForeignKey(
        ServiceCategory, 
        on_delete=models.PROTECT,
        related_name='services'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pricing
    price_per_1000 = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order = models.PositiveIntegerField(default=1)
    maximum_order = models.PositiveIntegerField(default=10000)
    
    # Service details
    service_type = models.CharField(max_length=20, choices=ServiceType.choices)
    speed = models.CharField(max_length=10, choices=Speed.choices, default=Speed.MEDIUM)
    quality = models.CharField(max_length=10, choices=Quality.choices, default=Quality.HIGH)
    
    # Features
    refill_available = models.BooleanField(default=False)
    refill_days = models.PositiveIntegerField(default=30, help_text="Days within which refill is allowed")
    drip_feed_available = models.BooleanField(default=False)
    drip_feed_speed = models.PositiveIntegerField(
        null=True, blank=True, 
        help_text="Quantity per day for drip feed"
    )
    
    # API integration
    api_service_id = models.CharField(
        max_length=100, 
        help_text="Service ID from provider API",
        db_index=True
    )
    api_provider = models.CharField(max_length=50, default="default")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    requires_link = models.BooleanField(default=True, help_text="Whether this service needs a link/URL")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'services'
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['service_type']),
            models.Index(fields=['api_service_id']),
        ]
        ordering = ['category', 'price_per_1000']
    
    def __str__(self):
        return f"{self.name} - ${self.price_per_1000}/1K"
    
    def calculate_price(self, quantity):
        """Calculate price for a given quantity"""
        return (self.price_per_1000 * quantity) / 1000


# ==================== ORDER MODELS ====================

class Order(models.Model):
    """Customer orders"""
    
    class OrderStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        PARTIAL = 'partial', 'Partially Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
        ERROR = 'error', 'Error'
    
    # Order identifiers
    order_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='orders')
    description = models.CharField(max_length=90,null=True, blank=True)
    # Order details
    link = models.URLField(max_length=500, help_text="Social media post/profile link")
    quantity = models.PositiveIntegerField()
    charge = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status tracking
    status = models.CharField(
        max_length=20, 
        choices=OrderStatus.choices, 
        default=OrderStatus.PENDING
    )
    
    # Progress tracking
    start_count = models.PositiveIntegerField(
        default=0, 
        help_text="Starting count before order"
    )
    current_count = models.PositiveIntegerField(
        default=0, 
        help_text="Current delivered count"
    )
    remains = models.PositiveIntegerField(
        default=0, 
        help_text="Remaining to deliver"
    )
    
    # Drip feed
    is_drip_feed = models.BooleanField(default=False)
    drip_feed_quantity = models.PositiveIntegerField(
        null=True, blank=True, 
        help_text="Quantity per day for drip feed"
    )
    drip_feed_runs = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Number of drip feed runs completed"
    )
    
    # API tracking
    api_order_id = models.CharField(
        max_length=100, 
        null=True, blank=True,
        help_text="Order ID from provider API",
        db_index=True
    )
    api_response = models.JSONField(null=True, blank=True)
    
    # Additional info
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['api_order_id']),
            models.Index(fields=['order_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order {self.order_id} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = self.generate_order_id()
        if self.status == self.OrderStatus.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_order_id():
        """Generate a unique order ID"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD-{timestamp}-{random_str}"
    
    def update_progress(self, delivered_count):
        """Update order progress"""
        self.current_count = delivered_count
        self.remains = max(0, self.quantity - delivered_count)
        
        if self.remains == 0:
            self.status = self.OrderStatus.COMPLETED
            self.completed_at = timezone.now()
        elif self.current_count > 0:
            self.status = self.OrderStatus.IN_PROGRESS
        
        self.save()


# ==================== TRANSACTION MODELS ====================

class Transaction(models.Model):
    """Financial transactions"""
    
    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        REFUND = 'refund', 'Refund'
        ORDER_PAYMENT = 'order_payment', 'Order Payment'
        BONUS = 'bonus', 'Bonus'
    
    class PaymentMethod(models.TextChoices):
        PAYPAL = 'paypal', 'PayPal'
        STRIPE = 'stripe', 'Stripe'
        CRYPTO = 'crypto', 'Cryptocurrency'
        CREDIT_CARD = 'credit_card', 'Credit Card'
        BALANCE = 'balance', 'Balance Transfer'
        MANUAL = 'manual', 'Manual'
    
    class TransactionStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
    
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transactions')
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='transactions'
    )
    
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices)
    
    # Payment gateway details
    gateway_transaction_id = models.CharField(max_length=255, null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['gateway_transaction_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transaction_id():
        """Generate a unique transaction ID"""
        import uuid
        return f"TXN-{uuid.uuid4().hex[:12].upper()}"
    
class ChildPanel(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='child_panels')
    domain = models.CharField(max_length=255, unique=True)
    currency = models.CharField(max_length=10, default='USD')
    admin_username = models.CharField(max_length=100)
    api_key = models.CharField(max_length=100,unique=True, null=True, blank=True)
    # Never store plain text passwords - use Django's password hashing
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    nameserver1 = models.CharField(max_length=255, default='ns1.perfectdns.com')
    nameserver2 = models.CharField(max_length=255, default='ns2.perfectdns.com')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.domain} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']

# ==================== REVIEW MODELS ====================

class Review(models.Model):
    """Customer reviews/testimonials"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviews')
    author_name = models.CharField(max_length=100)
    author_avatar = models.URLField(max_length=500, null=True, blank=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    content = models.TextField()
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reviews'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review by {self.author_name} - {self.rating}★"


# ==================== FAQ MODELS ====================

class FAQ(models.Model):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=100, default="General")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'faqs'
        ordering = ['display_order', 'id']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
    
    def __str__(self):
        return self.question


# ==================== API LOG MODELS ====================

class APILog(models.Model):
    """Log of API calls to providers"""
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    endpoint = models.CharField(max_length=255)
    request_data = models.JSONField()
    response_data = models.JSONField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_logs'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['success']),
        ]
        ordering = ['-created_at']


# ==================== SETTINGS MODELS ====================

class SiteSetting(models.Model):
    """Site-wide settings"""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'site_settings'
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Get a setting value by key"""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
# ==================== ADD THESE MODELS TO MODELS.PY ====================


class Affiliate(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate')
    referral_code = models.CharField(max_length=20, unique=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    available_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    min_payout = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.referral_code}"


class ReferralVisit(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='visits')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']


class Referral(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='referrals')
    referred_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='referred_by')
    converted = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    commission_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.affiliate.user.username} -> {self.referred_user.username if self.referred_user else 'Guest'}"


class AffiliatePayout(models.Model):
    PAYOUT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYOUT_METHODS = [
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('payoneer', 'Payoneer'),
    ]
    
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYOUT_METHODS, default='bank_transfer')
    payment_details = models.TextField(blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payout {self.id} - {self.affiliate.user.username} - {self.amount}"

