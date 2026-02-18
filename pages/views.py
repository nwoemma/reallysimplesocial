from django.shortcuts import render,redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect,HttpResponse
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
import json
from django.db.models import Prefetch
from users.smm import SMMApi
from django.db import transaction
from django.core.paginator import Paginator
from .utils import generate_transaction_id
import secrets
from decimal import Decimal
import string
import random
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from .forms import AddFundsForm
from .models import Notification
from django.contrib.auth import get_user_model
from users.models import (Order,ServiceCategory,Service,Transaction,PaymentGateway,Affiliate,
AffiliatePayout,Referral,ReferralVisit,ChildPanel,SiteSetting)
from django.contrib.auth.decorators import login_required

User=get_user_model()

def instragram_followers(request):
    page_title ="Instragram followers"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/instragram-followers.html')
def tiktok_followers(request):
    page_title = "Tiktok followers"
    context={
        'page_title':page_title
    }
    return render(request,'pages/tiktok-followers.html')
def twitter_followers(request):
    page_title = "Twitters followers"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/twitter-followers.html')
@login_required
def account(request):
    """Main account settings page"""
    page_title = "Account Settings"
    
    context = {
        'page_title': page_title,
        'user': request.user,
    }
    return render(request, "pages/account.html", context)


@login_required
def notifications(request):
    """Notifications settings page"""
    page_title = "Notification Settings"
    
    # Get user's notifications
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(notifications_list, 10)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'user': request.user,
        'notifications': notifications_page,
        'csrf_token': request.COOKIES.get('csrftoken', ''),
    }
    return render(request, "pages/notifications.html", context)


@login_required
def update_notifications(request):
    """Update notification preferences"""
    if request.method == 'POST':
        # Get checkbox values (they return 'on' if checked)
        request.user.email_notifications = request.POST.get('email_notifications') == 'on'
        request.user.order_completed_notify = request.POST.get('order_completed_notify') == 'on'
        request.user.order_processing_notify = request.POST.get('order_processing_notify') == 'on'
        request.user.order_partial_notify = request.POST.get('order_partial_notify') == 'on'
        request.user.order_cancelled_notify = request.POST.get('order_cancelled_notify') == 'on'
        request.user.deposit_success_notify = request.POST.get('deposit_success_notify') == 'on'
        request.user.low_balance_notify = request.POST.get('low_balance_notify') == 'on'
        request.user.login_alert_notify = request.POST.get('login_alert_notify') == 'on'
        request.user.marketing_emails = request.POST.get('marketing_emails') == 'on'
        request.user.newsletter = request.POST.get('newsletter') == 'on'
        
        request.user.save()
        
        messages.success(request, '✅ Notification settings updated successfully!')
        
    return redirect('pages:notifications')

# ==================== EMAIL MANAGEMENT ====================

@login_required
def change_email(request):
    """Handle email change request"""
    if request.method == 'POST':
        new_email = request.POST.get('new_email')
        password = request.POST.get('password')
        
        # Verify password
        if not request.user.check_password(password):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid password'})
            messages.error(request, 'Invalid password')
            return redirect('pages:account')
        
        # Check if email already exists
        if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Email already in use'})
            messages.error(request, 'Email already in use')
            return redirect('pages:account')
        
        # Update email
        request.user.email = new_email
        request.user.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'email': new_email})
        
        messages.success(request, 'Email updated successfully')
        return redirect('pages:account')
    
    return redirect('pages:account')


# ==================== API KEY MANAGEMENT ====================

@login_required
def generate_api_key(request):
    """Generate a new API key for the user"""
    if request.method == 'POST':
        # Generate random API key and secret
        api_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        api_secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        request.user.api_key = api_key
        request.user.api_secret = api_secret
        request.user.save()
        
        messages.success(request, 'New API key generated successfully')
    
    return redirect('pages:account')


# ==================== TWO-FACTOR AUTHENTICATION ====================

@login_required
def two_factor_generate(request):
    """Generate and send 2FA code"""
    if request.method == 'POST':
        enabled = request.POST.get('enabled') == '1'
        
        if enabled and not request.user.two_factor_enabled:
            # Generate a random 6-digit code
            import random
            code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Store code in session (expires in 10 minutes)
            request.session['2fa_code'] = code
            request.session['2fa_code_expiry'] = (timezone.now() + timezone.timedelta(minutes=10)).timestamp()
            
            # Send email with code
            send_2fa_email(request.user.email, code)  # Implement this function
            
            return JsonResponse({
                'success': True,
                'requires_approval': True,
                'message': 'Verification code sent to your email'
            })
        
        elif not enabled and request.user.two_factor_enabled:
            # Disable 2FA
            request.user.two_factor_enabled = False
            request.user.save()
            
            messages.success(request, 'Two-factor authentication disabled')
            return redirect('pages:account')
    
    return redirect('pages:account')


@login_required
def two_factor_approve(request):
    """Approve 2FA with code"""
    if request.method == 'POST':
        code = request.POST.get('code')
        stored_code = request.session.get('2fa_code')
        expiry = request.session.get('2fa_code_expiry')
        
        # Check if code exists and not expired
        if not stored_code or not expiry or timezone.now().timestamp() > expiry:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Code expired. Please try again.'})
            messages.error(request, 'Code expired. Please try again.')
            return redirect('pages:account')
        
        # Verify code
        if code == stored_code:
            request.user.two_factor_enabled = True
            request.user.save()
            
            # Clear session
            del request.session['2fa_code']
            del request.session['2fa_code_expiry']
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
            messages.success(request, 'Two-factor authentication enabled')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid code'})
            messages.error(request, 'Invalid code')
    
    return redirect('pages:account')


@login_required
def two_factor_disable(request):
    """Disable 2FA"""
    if request.method == 'POST':
        request.user.two_factor_enabled = False
        request.user.save()
        messages.success(request, 'Two-factor authentication disabled')
    
    return redirect('pages:account')


# Helper function to send 2FA email
def send_2fa_email(email, code):
    """Send 2FA code via email"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = 'Your Two-Factor Authentication Code'
    message = f'''
    Your verification code is: {code}
    
    This code will expire in 10 minutes.
    If you didn't request this, please ignore this email.
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


# ==================== LANGUAGE SETTINGS ====================

@login_required
def update_language(request):
    """Update user language preference"""
    if request.method == 'POST':
        language = request.POST.get('language')
        
        # Validate language
        valid_languages = ['en']  # Add more as needed
        if language in valid_languages:
            request.user.language = language  # Add this field to your User model
            request.user.save()
            messages.success(request, 'Language updated successfully')
        else:
            messages.error(request, 'Invalid language selection')
    
    return redirect('pages:account')


# ==================== TIMEZONE SETTINGS ====================

@login_required
def update_timezone(request):
    """Update user timezone"""
    if request.method == 'POST':
        timezone_offset = request.POST.get('timezone')
        
        # Store timezone preference
        request.user.timezone = timezone_offset  # Add this field to your User model
        request.user.save()
        
        messages.success(request, 'Timezone updated successfully')
    
    return redirect('pages:account')


# ==================== PASSWORD MANAGEMENT ====================

@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect')
            return redirect('pages:account')
        
        # Check new password match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
            return redirect('pages:account')
        
        # Validate password strength (optional)
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
            return redirect('pages:account')
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Keep user logged in
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password changed successfully')
    
    return redirect('pages:account')
def services(request):
    page_title = "Serivces"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/services.html')
def how_tos(request):
    page_title = "how to use reallysimplesocial"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/how-to-use-reallysimplesocial.html')
def test_view(request):
    from django.http import HttpResponse
    return HttpResponse(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

def orders(request):
    page_title = 'Orders'
    user = request.user
    
    # Get all orders for this user
    orders_list = Order.objects.filter(user=user).select_related('service').order_by('-created_at')
    
    # Pagination - 15 orders per page
    paginator = Paginator(orders_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics for header
    total_spent = user.total_spent or 0
    current_balance = user.balance or 0
    total_orders = user.total_orders or 0
    
    context = {
        'page_title': page_title,
        # Header stats - your template uses these exact names
        'username': user.username,
        'spent_balance': total_spent,
        'account_balance': current_balance,
        'order_count': total_orders,
        # Orders data - MUST be 'orders' for the template loop
        'orders': page_obj,  # This is what the template expects
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status': 'all',
        'search_query': request.GET.get('search', ''),
    }
    
    print("Context keys:", context.keys())  # Debug
    return render(request, 'pages/dashboard-orders.html', context)




@login_required
def dashboard_new_order(request):
    page_title = "New Order"
    
    # ==================== HANDLE ORDER SUBMISSION (POST) ====================
    if request.method == 'POST':
        print("="*50)
        print("PROCESSING ORDER SUBMISSION")
        print("POST data:", request.POST)
        print("User:", request.user)
        print("User Balance:", request.user.balance)
        print("="*50)
        
        # Get form data
        service_id = request.POST.get('service_id')
        link = request.POST.get('link')
        quantity = request.POST.get('quantity')
        
        print(f"service_id: {service_id}")
        print(f"link: {link}")
        print(f"quantity: {quantity}")
        
        # Validate required fields
        if not all([service_id, link, quantity]):
            print("❌ Missing required fields")
            messages.error(request, 'All fields are required')
            return redirect('pages:new-order')
        
        print("✅ All fields present")
        
        try:
            # Get service
            print(f"Fetching service with ID: {service_id}")
            service = Service.objects.get(id=service_id, is_active=True)
            print(f"✅ Service found: {service.name}")
            print(f"   Price per 1000: {service.price_per_1000}")
            print(f"   Min: {service.minimum_order}, Max: {service.maximum_order}")
            
            # Validate quantity
            try:
                quantity = int(quantity)
                print(f"✅ Quantity parsed: {quantity}")
                
                if quantity <= 0:
                    print("❌ Quantity is negative or zero")
                    messages.error(request, 'Quantity must be positive')
                    return redirect('pages:new-order')
            except ValueError as e:
                print(f"❌ Quantity parsing error: {e}")
                messages.error(request, 'Invalid quantity format')
                return redirect('pages:new-order')
            
            # Check min/max limits
            if quantity < service.minimum_order:
                print(f"❌ Quantity {quantity} < minimum {service.minimum_order}")
                messages.error(request, f'Minimum order is {service.minimum_order}')
                return redirect('pages:new-order')
                
            if quantity > service.maximum_order:
                print(f"❌ Quantity {quantity} > maximum {service.maximum_order}")
                messages.error(request, f'Maximum order is {service.maximum_order}')
                return redirect('pages:new-order')
            
            print("✅ Quantity within limits")
            
            # Calculate price
            price_per_unit = service.price_per_1000 / 1000
            total_price = Decimal(str(quantity)) * Decimal(str(price_per_unit))
            print(f"💰 Price calculation:")
            print(f"   Price per 1000: {service.price_per_1000}")
            print(f"   Price per unit: {price_per_unit}")
            print(f"   Total price: {total_price}")
            
            # Check user balance
            print(f"💳 User balance: {request.user.balance}")
            print(f"💳 Required: {total_price}")
            
            if request.user.balance < total_price:
                print(f"❌ Insufficient balance")
                messages.error(request, f'Insufficient balance. You need ${total_price} but have ${request.user.balance}')
                return redirect('pages:new-order')
            
            print("✅ Balance sufficient")
            
            # Use transaction
            with transaction.atomic():
                # CREATE THE ORDER
                print(f"📝 Creating order...")
                
                order = Order.objects.create(
                    user=request.user,
                    service=service,
                    link=link,
                    quantity=quantity,
                    charge=total_price,
                    status='pending',
                    remains=quantity,
                )
                
                
                print(f"✅ Order created!")
                print(f"   Order ID: {order.order_id}")
                print(f"   Order PK: {order.id}")
                smm = SMMApi()
                api_response = smm.add_order(
                    service_id=service.api_service_id,  # Provider's service ID
                    link=link,
                    quantity=quantity
                )
                print("API Response",api_response)
                # Deduct from user balance
                print(f"💰 Updating user balance...")
                old_balance = request.user.balance
                request.user.balance -= total_price
                request.user.total_spent += total_price
                request.user.total_orders += 1
                request.user.save()
                
                print(f"✅ Balance updated: ${old_balance} → ${request.user.balance}")
                
                # Create transaction record
                print(f"📝 Creating transaction...")
                transaction_id = generate_transaction_id()
                
                transaction_obj = Transaction.objects.create(
                    user=request.user,
                    amount=total_price,
                    transaction_type='order_payment',
                    status='completed',
                    description=f'Payment for order #{order.order_id} - {service.name}',
                    transaction_id=transaction_id,
                    order=order,
                    payment_method='balance'
                )
                
                print(f"✅ Transaction created: {transaction_obj.transaction_id}")
                print("="*50)
                print("🎉 ORDER SUCCESSFULLY CREATED!")
                print("="*50)
                
                messages.success(request, f'Order #{order.order_id} placed successfully!')
                
                print(f"🔄 Redirecting to order detail: {order.order_id}")
                return redirect('pages:order_detail', order_id=order.order_id)
                
        except Service.DoesNotExist:
            print(f"❌ Service not found with ID: {service_id}")
            messages.error(request, 'Service not found')
            return redirect('pages:new-order')
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            messages.error(request, f'Error creating order: {str(e)}')
            return redirect('pages:new-order')
    
    # ... rest of GET code ...    
    # ==================== HANDLE SERVICE SELECTION (GET) ====================
    categories = ServiceCategory.objects.filter(is_active=True)
    
    selected_category_id = request.GET.get('category')
    services_for_category = []
    
    if selected_category_id:
        services_for_category = Service.objects.filter(
            category_id=selected_category_id,
            is_active=True
        ).order_by('name')
    
    service_description = None
    selected_service = None
    service_id = request.GET.get('service')
    
    if service_id:
        try:
            selected_service = Service.objects.get(id=service_id, is_active=True)
            service_description = selected_service.description
        except Service.DoesNotExist:
            pass
    
    context = {
        'page_title': page_title,
        'categories': categories,
        'services_for_category': services_for_category,
        'service_description': service_description,
        'selected_service': selected_service,
    }
    
    return render(request, "pages/dashboard-new-order.html", context)

def dashboard_services(request):
    page_title = "Services"
    active_services = Service.objects.filter(is_active=True).order_by('name')
    
    categories = ServiceCategory.objects.filter(
        is_active=True
    ).prefetch_related(
        Prefetch('services', queryset=active_services, to_attr='active_services')
    )
    
    # Only include categories that have active services
    categories_with_services = [c for c in categories if c.active_services]
    
    context = {
        'page_title': page_title,
        'categories': categories_with_services,
        'total_services': active_services.count(),
    }
    return render(request, 'pages/dashboard-services.html', context )
def dashboard_add_funds(request):
    page_title = "Add funds"
    transaction = Transaction.objects.filter(
        user=request.user,
        transaction_type='deposit'
    ).order_by('-created_at')
    payment_method_count = PaymentGateway.objects.filter(is_active=True).count()
    # Handle form submission
    if request.method == "POST":
        form = AddFundsForm(request.POST)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            amount= form.cleaned_data['amount']
            
            transaction = Transaction.objects.create(
                user=request.user,
                amount=amount,
                transaction_type='deposit',
                payment_method=payment_method,
                status='pending',
                transaction_id=generate_transaction_id()
            )
            return redirect('pages:process_payment', transaction_id=transaction.transaction_id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = AddFundsForm()
    
    # Get available payment gateways
    payment_gateways = PaymentGateway.objects.filter(is_active=True)
    
    # Prepare payment methods data for JavaScript
    payment_methods_data = {}
    for gateway in payment_gateways:
        payment_methods_data[str(gateway.id)] = {
            'name': gateway.name,
            'code': gateway.code,
            'commission': {
                'is_enabled': gateway.commission_enabled,
                'fixed': float(gateway.commission_fixed) if gateway.commission_fixed else 0,
                'percent': float(gateway.commission_percent) if gateway.commission_percent else 0,
            },
            'instruction': gateway.instructions,
            'min_amount': float(gateway.min_amount) if gateway.min_amount else 0,
            'max_amount': float(gateway.max_amount) if gateway.max_amount else 1000000,
        }
    
    context = {
        'page_title': page_title,
        'user': request.user,
        'transactions':transaction,
        'payment_methods_count': payment_method_count,
        'payment_gateways': payment_gateways,
        'payment_methods_json': json.dumps(payment_methods_data),
        'form': form,
    }
    print(context)
    return render(request, "pages/dashboard-add-funds.html", context)

# ==================== TRANSACTION HISTORY VIEW ====================

@login_required
def transaction_history(request):
    """View all transactions with pagination"""
    page_title = "Transaction History"
    
    transactions_list = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(transactions_list, 15)
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'transactions': transactions,
        'is_paginated': transactions.has_other_pages(),
    }
    return render(request, "pages/transaction-history.html", context)


# ==================== PAYMENT PROCESSING ====================

@login_required
def process_payment(request, transaction_id):
    """Process payment through selected gateway"""
    try:
        transaction = Transaction.objects.get(
            transaction_id=transaction_id,
            user=request.user,
            status='pending'
        )
    except Transaction.DoesNotExist:
        messages.error(request, 'Invalid transaction')
        return redirect('pages:add_funds')
    
    # Get payment gateway
    gateway = PaymentGateway.objects.filter(
        id=transaction.payment_method,
        is_active=True
    ).first()
    
    if not gateway:
        messages.error(request, 'Payment method not available')
        return redirect('pages:add_funds')
    
    # Route to specific gateway processor
    if gateway.code == 'korapay':
        return process_korapay_payment(request, transaction, gateway)
    elif gateway.code == 'transactpay':
        return process_transactpay_payment(request, transaction, gateway)
    elif gateway.code == 'flutterwave':
        return process_flutterwave_payment(request, transaction, gateway)
    else:
        messages.error(request, 'Unsupported payment method')
        return redirect('pages:add_funds')


# ==================== KORAPAY INTEGRATION ====================

def process_korapay_payment(request, transaction, gateway):
    """Process payment via Korapay"""
    import requests
    
    # Korapay API endpoint
    api_url = gateway.api_endpoint or "https://api.korapay.com/v1/charges/initialize"
    
    # Prepare payment data
    payment_data = {
        "reference": transaction.transaction_id,
        "amount": float(transaction.amount),
        "currency": "NGN",
        "redirect_url": request.build_absolute_uri(reverse('pages:payment_callback')),
        "customer": {
            "name": request.user.username,
            "email": request.user.email,
        }
    }
    
    headers = {
        "Authorization": f"Bearer {gateway.secret_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(api_url, json=payment_data, headers=headers)
        result = response.json()
        
        if result.get('status') and result.get('data', {}).get('checkout_url'):
            # Store gateway response
            transaction.gateway_response = result
            transaction.save()
            
            # Redirect to Korapay checkout
            return redirect(result['data']['checkout_url'])
        else:
            messages.error(request, f"Payment initialization failed: {result.get('message', 'Unknown error')}")
            return redirect('pages:add_funds')
            
    except Exception as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect('pages:add_funds')


# ==================== TRANSACTPAY INTEGRATION ====================

def process_transactpay_payment(request, transaction, gateway):
    """Process payment via TransactPay"""
    # TransactPay uses their JS SDK, so we render a template
    context = {
        'transaction': transaction,
        'gateway': gateway,
        'public_key': gateway.public_key,
        'amount': float(transaction.amount),
        'currency': 'NGN',
        'reference': transaction.transaction_id,
        'customer_email': request.user.email,
        'customer_name': request.user.username,
        'callback_url': request.build_absolute_uri(reverse('pages:payment_callback')),
    }
    return render(request, "pages/transactpay-checkout.html", context)


# ==================== FLUTTERWAVE INTEGRATION ====================

def process_flutterwave_payment(request, transaction, gateway):
    """Process payment via Flutterwave"""
    import requests
    
    api_url = gateway.api_endpoint or "https://api.flutterwave.com/v3/payments"
    
    payment_data = {
        "tx_ref": transaction.transaction_id,
        "amount": float(transaction.amount),
        "currency": "NGN",
        "redirect_url": request.build_absolute_uri(reverse('pages:payment_callback')),
        "customer": {
            "email": request.user.email,
            "name": request.user.username,
        },
        "customizations": {
            "title": "Add Funds",
            "description": f"Add funds to {request.user.username}'s account"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {gateway.secret_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(api_url, json=payment_data, headers=headers)
        result = response.json()
        
        if result.get('status') == 'success' and result.get('data', {}).get('link'):
            transaction.gateway_response = result
            transaction.save()
            
            return redirect(result['data']['link'])
        else:
            messages.error(request, f"Payment initialization failed")
            return redirect('pages:add_funds')
            
    except Exception as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect('pages:add_funds')


# ==================== PAYMENT CALLBACK ====================

@login_required
@csrf_exempt
def payment_callback(request):
    """Handle payment callback from gateway"""
    if request.method == 'GET':
        # Handle GET callback (redirect)
        reference = request.GET.get('reference') or request.GET.get('tx_ref')
        status = request.GET.get('status')
        
        if reference:
            try:
                transaction = Transaction.objects.get(transaction_id=reference, user=request.user)
                
                if status == 'success' or status == 'completed':
                    # Verify payment with gateway
                    return verify_payment(request, transaction)
                else:
                    transaction.status = 'failed'
                    transaction.save()
                    messages.error(request, 'Payment failed or cancelled')
            except Transaction.DoesNotExist:
                messages.error(request, 'Transaction not found')
        
        return redirect('pages:add_funds')
    
    elif request.method == 'POST':
        # Handle webhook callback
        return payment_webhook(request)


# ==================== PAYMENT VERIFICATION ====================

@login_required
def verify_payment(request, transaction):
    """Verify payment with gateway"""
    gateway = PaymentGateway.objects.get(id=transaction.payment_method)
    
    if gateway.code == 'korapay':
        return verify_korapay_payment(request, transaction, gateway)
    elif gateway.code == 'transactpay':
        return verify_transactpay_payment(request, transaction, gateway)
    elif gateway.code == 'flutterwave':
        return verify_flutterwave_payment(request, transaction, gateway)
    
    return redirect('pages:add_funds')


def verify_korapay_payment(request, transaction, gateway):
    """Verify Korapay payment"""
    import requests
    
    api_url = f"https://api.korapay.com/v1/charges/{transaction.transaction_id}"
    headers = {"Authorization": f"Bearer {gateway.secret_key}"}
    
    try:
        response = requests.get(api_url, headers=headers)
        result = response.json()
        
        if result.get('status') and result.get('data', {}).get('status') == 'success':
            # Complete transaction
            transaction.status = 'completed'
            transaction.save()
            
            # Add funds to user balance
            request.user.balance += Decimal(str(transaction.amount))
            request.user.save()
            
            messages.success(request, f'₦{transaction.amount} added to your account successfully!')
        else:
            transaction.status = 'failed'
            transaction.save()
            messages.error(request, 'Payment verification failed')
            
    except Exception as e:
        transaction.status = 'failed'
        transaction.save()
        messages.error(request, f'Verification error: {str(e)}')
    
    return redirect('pages:add_funds')


def verify_transactpay_payment(request, transaction, gateway):
    """Verify TransactPay payment"""
    import requests
    
    api_url = f"{gateway.api_endpoint or 'https://api.transactpay.ai/v1'}/transactions/{transaction.transaction_id}/verify"
    headers = {"Authorization": f"Bearer {gateway.secret_key}"}
    
    try:
        response = requests.get(api_url, headers=headers)
        result = response.json()
        
        if result.get('status') == 'success':
            transaction.status = 'completed'
            transaction.save()
            
            request.user.balance += Decimal(str(transaction.amount))
            request.user.save()
            
            messages.success(request, f'₦{transaction.amount} added to your account successfully!')
        else:
            transaction.status = 'failed'
            transaction.save()
            messages.error(request, 'Payment verification failed')
            
    except Exception as e:
        transaction.status = 'failed'
        transaction.save()
        messages.error(request, f'Verification error: {str(e)}')
    
    return redirect('pages:add_funds')


def verify_flutterwave_payment(request, transaction, gateway):
    """Verify Flutterwave payment"""
    import requests
    
    api_url = f"https://api.flutterwave.com/v3/transactions/{transaction.transaction_id}/verify"
    headers = {"Authorization": f"Bearer {gateway.secret_key}"}
    
    try:
        response = requests.get(api_url, headers=headers)
        result = response.json()
        
        if result.get('status') == 'success' and result.get('data', {}).get('status') == 'successful':
            transaction.status = 'completed'
            transaction.save()
            
            request.user.balance += Decimal(str(transaction.amount))
            request.user.save()
            
            messages.success(request, f'₦{transaction.amount} added to your account successfully!')
        else:
            transaction.status = 'failed'
            transaction.save()
            messages.error(request, 'Payment verification failed')
            
    except Exception as e:
        transaction.status = 'failed'
        transaction.save()
        messages.error(request, f'Verification error: {str(e)}')
    
    return redirect('pages:add_funds')


# ==================== PAYMENT WEBHOOK ====================

@csrf_exempt
def payment_webhook(request):
    """Handle webhook callbacks from payment gateways"""
    if request.method == 'POST':
        payload = json.loads(request.body)
        signature = request.headers.get('X-Signature')
        
        # Verify webhook signature based on gateway
        gateway_code = request.GET.get('gateway')
        
        if gateway_code == 'korapay':
            return handle_korapay_webhook(payload, signature)
        elif gateway_code == 'transactpay':
            return handle_transactpay_webhook(payload, signature)
        elif gateway_code == 'flutterwave':
            return handle_flutterwave_webhook(payload, signature)
    
    return HttpResponse(status=400)


def handle_korapay_webhook(payload, signature):
    """Handle Korapay webhook"""
    event = payload.get('event')
    data = payload.get('data', {})
    reference = data.get('reference')
    
    if event == 'charge.success' and reference:
        try:
            transaction = Transaction.objects.get(transaction_id=reference)
            
            # Verify signature (implement actual verification)
            
            if transaction.status == 'pending':
                transaction.status = 'completed'
                transaction.save()
                
                # Add funds
                user = transaction.user
                user.balance += Decimal(str(transaction.amount))
                user.save()
                
        except Transaction.DoesNotExist:
            pass
    
    return HttpResponse(status=200)


def handle_transactpay_webhook(payload, signature):
    """Handle TransactPay webhook"""
    reference = payload.get('reference')
    status = payload.get('status')
    
    if status == 'success' and reference:
        try:
            transaction = Transaction.objects.get(transaction_id=reference)
            
            if transaction.status == 'pending':
                transaction.status = 'completed'
                transaction.save()
                
                user = transaction.user
                user.balance += Decimal(str(transaction.amount))
                user.save()
                
        except Transaction.DoesNotExist:
            pass
    
    return HttpResponse(status=200)


def handle_flutterwave_webhook(payload, signature):
    """Handle Flutterwave webhook"""
    event = payload.get('event')
    data = payload.get('data', {})
    reference = data.get('tx_ref')
    
    if event == 'charge.completed' and reference:
        try:
            transaction = Transaction.objects.get(transaction_id=reference)
            
            if data.get('status') == 'successful' and transaction.status == 'pending':
                transaction.status = 'completed'
                transaction.save()
                
                user = transaction.user
                user.balance += Decimal(str(transaction.amount))
                user.save()
                
        except Transaction.DoesNotExist:
            pass
    
    return HttpResponse(status=200)
    
@login_required
def dashboard_affiliates(request):
    """Main affiliates dashboard page"""
    page_title = "Affiliates"
    
    # Get or create affiliate profile for user
    affiliate, created = Affiliate.objects.get_or_create(
        user=request.user,
        defaults={
            'referral_code': generate_referral_code(),
            'commission_rate': Decimal('10.0'),  # 10% default
            'total_earnings': Decimal('0.00'),
            'available_earnings': Decimal('0.00'),
            'min_payout': Decimal('1000.00'),
        }
    )
    
    # Get statistics
    total_visits = ReferralVisit.objects.filter(affiliate=affiliate).count()
    total_registrations = Referral.objects.filter(
        affiliate=affiliate,
        converted=True
    ).count()
    total_referrals = Referral.objects.filter(affiliate=affiliate).count()
    
    # Calculate conversion rate
    conversion_rate = 0
    if total_visits > 0:
        conversion_rate = (total_registrations / total_visits) * 100
    
    # Get total earnings from successful referrals
    total_earnings = Referral.objects.filter(
        affiliate=affiliate,
        converted=True,
        commission_paid=True
    ).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')
    
    # Update affiliate totals if needed
    if affiliate.total_earnings != total_earnings:
        affiliate.total_earnings = total_earnings
        affiliate.save()
    
    # Get payout history
    payouts_list = AffiliatePayout.objects.filter(affiliate=affiliate).order_by('-created_at')
    
    # Pagination for payouts
    paginator = Paginator(payouts_list, 10)
    page_number = request.GET.get('page')
    payouts = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'affiliate': affiliate,
        'total_visits': total_visits,
        'total_registrations': total_registrations,
        'total_referrals': total_referrals,
        'conversion_rate': conversion_rate,
        'total_earnings': total_earnings,
        'available_earnings': affiliate.available_earnings,
        'commission_rate': affiliate.commission_rate,
        'min_payout': affiliate.min_payout,
        'payouts': payouts,
        'is_paginated': payouts.has_other_pages(),
    }
    return render(request, 'pages/dashboard-affiliates.html', context)


# ==================== REFERRAL TRACKING VIEWS ====================
@login_required
def referral_redirect(request, referral_code):
    """Handle referral link clicks"""
    try:
        affiliate = Affiliate.objects.get(referral_code=referral_code, is_active=True)
        
        # Track visit
        ReferralVisit.objects.create(
            affiliate=affiliate,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=request.META.get('HTTP_REFERER', ''),
        )
        
        # Store affiliate ID in session
        request.session['ref_affiliate'] = affiliate.id
        
        # Redirect to signup page
        return redirect('pages:signup')
        
    except Affiliate.DoesNotExist:
        # Invalid referral code, redirect to home
        return redirect('pages:home')


@login_required
def track_referral_conversion(request):
    """Track when a referred user signs up"""
    affiliate_id = request.session.get('ref_affiliate')
    
    if affiliate_id:
        try:
            affiliate = Affiliate.objects.get(id=affiliate_id)
            
            # Check if this user was already referred
            existing_referral = Referral.objects.filter(referred_user=request.user).first()
            
            if not existing_referral:
                # Create referral record
                referral = Referral.objects.create(
                    affiliate=affiliate,
                    referred_user=request.user,
                    converted=True,
                    converted_at=timezone.now()
                )
                
                # Clear session
                del request.session['ref_affiliate']
                
                return True
        except Affiliate.DoesNotExist:
            pass
    
    return False


# ==================== AFFILIATE STATISTICS ====================

@login_required
def affiliate_referrals(request):
    """View list of referrals"""
    page_title = "My Referrals"
    
    affiliate = Affiliate.objects.get(user=request.user)
    referrals_list = Referral.objects.filter(affiliate=affiliate).order_by('-created_at')
    
    paginator = Paginator(referrals_list, 20)
    page_number = request.GET.get('page')
    referrals = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'referrals': referrals,
        'is_paginated': referrals.has_other_pages(),
    }
    return render(request, 'pages/affiliate-referrals.html', context)


@login_required
def affiliate_visits(request):
    """View list of referral visits"""
    page_title = "Referral Visits"
    
    affiliate = Affiliate.objects.get(user=request.user)
    visits_list = ReferralVisit.objects.filter(affiliate=affiliate).order_by('-created_at')
    
    paginator = Paginator(visits_list, 20)
    page_number = request.GET.get('page')
    visits = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'visits': visits,
        'is_paginated': visits.has_other_pages(),
    }
    return render(request, 'pages/affiliate-visits.html', context)


# ==================== PAYOUT REQUESTS ====================

@login_required
def request_payout(request):
    """Request affiliate payout"""
    if request.method == 'POST':
        try:
            affiliate = Affiliate.objects.get(user=request.user)
            
            # Check minimum payout
            if affiliate.available_earnings < affiliate.min_payout:
                messages.error(request, f'Minimum payout amount is NGN {affiliate.min_payout}')
                return redirect('pages:affiliates')
            
            # Create payout request
            payout = AffiliatePayout.objects.create(
                affiliate=affiliate,
                amount=affiliate.available_earnings,
                status='pending',
                payment_method=request.POST.get('payment_method', 'bank_transfer'),
                payment_details=request.POST.get('payment_details', '')
            )
            
            # Deduct from available earnings
            affiliate.available_earnings = Decimal('0.00')
            affiliate.save()
            
            messages.success(request, f'Payout request for NGN {payout.amount} submitted successfully')
            
        except Affiliate.DoesNotExist:
            messages.error(request, 'Affiliate profile not found')
        except Exception as e:
            messages.error(request, f'Error requesting payout: {str(e)}')
    
    return redirect('pages:affiliates')


# ==================== HELPER FUNCTIONS ====================

def generate_referral_code(length=5):
    """Generate a unique referral code"""
    while True:
        # Generate random code
        chars = string.ascii_lowercase + string.digits
        code = ''.join(random.choices(chars, k=length))
        
        # Check if unique
        if not Affiliate.objects.filter(referral_code=code).exists():
            return code


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def dashboard_childpanels(request):
    page_title = "Child Panels"
    
    try:
        # Try to get price from SiteSetting model
        child_panel_price = SiteSetting.get_setting('child_panel_price', 18000.00)
    except:
        # Fallback to default
        child_panel_price = Decimal('18000.00')
    
    currencies = [
        ('USD', 'United States Dollars (USD)'),
        ('RUB', 'Russian Rubles (RUB)'),
        ('THB', 'Thai Baht (THB)'),
        ('TRY', 'Turkish Lira (TRY)'),
        ('EUR', 'Euro (EUR)'),
        ('IDR', 'Indonesian Rupiah (IDR)'),
        ('BRL', 'Brazilian Real (BRL)'),
        ('CNY', 'Chinese Yuan (CNY)'),
        ('KRW', 'South Korean Won (KRW)'),
        ('INR', 'Indian Rupee (INR)'),
        ('IRR', 'Iranian Rial (IRR)'),
        ('SAR', 'Saudi Arabia Riyal (SAR)'),
        ('PLN', 'Polish złoty (PLN)'),
        ('MYR', 'Malaysian Ringgit (MYR)'),
        ('GBP', 'Pound sterling (GBP)'),
        ('KWD', 'Kuwaiti dinar (KWD)'),
        ('SEK', 'Swedish krona (SEK)'),
        ('ILS', 'Israeli shekel (ILS)'),
        ('HKD', 'Hong Kong dollar (HKD)'),
        ('NGN', 'Nigerian naira (NGN)'),
        ('KES', 'Kenyan shilling (KES)'),
        ('JPY', 'Japanese Yen (JPY)'),
        ('ARS', 'Argentine peso (ARS)'),
        ('VND', 'Vietnamese đồng (VND)'),
        ('CAD', 'Canadian dollar (CAD)'),
        ('IQD', 'Iraqi dinar (IQD)'),
        ('TWD', 'New Taiwan Dollar (TWD)'),
        ('AZN', 'Azerbaijani manat (AZN)'),
        ('BYN', 'Belarusian ruble (BYN)'),
        ('KZT', 'Kazakhstani tenge (KZT)'),
        ('UAH', 'Ukrainian hryvnia (UAH)'),
        ('RON', 'Romanian leu (RON)'),
        ('AED', 'United Arab Emirates dirham (AED)'),
        ('COP', 'Colombian peso (COP)'),
        ('PKR', 'Pakistan Rupee (PKR)'),
        ('EGP', 'Egyptian Pound (EGP)'),
        ('PHP', 'Philippine peso (PHP)'),
        ('GHS', 'Ghanaian Cedi (GHS)'),
        ('BDT', 'Bangladeshi taka (BDT)'),
        ('MAD', 'Moroccan dirham (MAD)'),
        ('NPR', 'Nepalese Rupee (NPR)'),
        ('TND', 'Tunisian Dinar (TND)'),
        ('CLP', 'Chilean Peso (CLP)'),
        ('XOF', 'CFA Franc BCEAO (XOF)'),
        ('LYD', 'Libyan Dinar (LYD)'),
        ('TZS', 'Tanzanian shilling (TZS)'),
        ('MXN', 'Mexican peso (MXN)'),
        ('UGX', 'Ugandan shilling (UGX)'),
        ('ZAR', 'South African rand (ZAR)'),
        ('PGK', 'Papua New Guinean kina (PGK)'),
        ('RWF', 'Rwandan franc (RWF)'),
        ('XAF', 'Central African CFA franc (XAF)'),
        ('OMR', 'Omani rial (OMR)'),
        ('LAK', 'Laotian kip (LAK)'),
        ('UZS', 'Uzbekistan Sum (UZS)'),
        ('SDG', 'Sudanese pound (SDG)'),
        ('CZK', 'Czech koruna (CZK)'),
        ('SYP', 'Syrian pound (SYP)'),
        ('DKK', 'Danish krone (DKK)'),
        ('PEN', 'Peruvian sol (PEN)'),
        ('HUF', 'Hungarian forint (HUF)'),
        ('NOK', 'Norwegian krone (NOK)'),
        ('MZN', 'Mozambican metical (MZN)'),
        ('AOA', 'Angolan kwanza (AOA)'),
        ('YER', 'Yemeni Rial (YER)'),
        ('JOD', 'Jordanian dinar (JOD)'),
        ('MMK', 'Myanmar kyat (MMK)'),
    ]
    
    # ========== DEBUGGING ==========
    print("\n" + "="*60)
    print("🔍 CHILD PANEL VIEW CALLED")
    print(f"📌 Request method: {request.method}")
    print(f"📌 User: {request.user.username} (ID: {request.user.id})")
    print(f'User is superuser: {request.user.is_superuser}' )
    print(f'User is admin: {request.user.is_staff}')
    print(f"📌 User authenticated: {request.user.is_authenticated}")
    print(f"📌 Currencies defined: {len(currencies)} items")
    print(f"📌 First 5 currencies: {currencies[:5]}")
    print("="*60 + "\n")
    # ================================
    
    # Handle form submission
    if request.method == 'POST':
        # Get form data
        domain = request.POST.get('domain', '').strip()
        currency = request.POST.get('currency', 'USD')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        # ========== DEBUGGING ==========
        print("\n" + "="*60)
        print("📝 POST DATA RECEIVED")
        print(f"📌 domain: '{domain}'")
        print(f"📌 currency: '{currency}'")
        print(f"📌 username: '{username}'")
        print(f"📌 password: {'*' * len(password) if password else 'EMPTY'}")
        print(f"📌 password_confirm: {'*' * len(password_confirm) if password_confirm else 'EMPTY'}")
        print("="*60 + "\n")
        # ================================
        
        # Validate form data
        errors = []
        
        # Check if user has permission to create child panels
        if not hasattr(request.user, 'can_create_child_panels') or not request.user.can_create_child_panels:
            errors.append("You don't have permission to create child panels")
            print("❌ Permission error: User cannot create child panels")
        
        # Validate domain
        if not domain:
            errors.append("Domain is required")
            print("❌ Domain is empty")
        elif not is_valid_domain(domain):
            errors.append("Please enter a valid domain name")
            print(f"❌ Invalid domain format: {domain}")
        
        # Validate username
        if not username:
            errors.append("Admin username is required")
            print("❌ Username is empty")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters long")
            print(f"❌ Username too short: {len(username)} chars")
        
        # Validate password
        if not password:
            errors.append("Password is required")
            print("❌ Password is empty")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long")
            print(f"❌ Password too short: {len(password)} chars")
        elif password != password_confirm:
            errors.append("Passwords do not match")
            print("❌ Passwords do not match")
        
        # Check if domain already exists
        if ChildPanel.objects.filter(domain=domain).exists():
            errors.append("This domain is already registered")
            print(f"❌ Domain already exists: {domain}")
        
        # Check user balance
        price = Decimal('18000.00')
        print(f"💰 User balance: {request.user.balance}, Required: {price}")
        if request.user.balance < price:
            errors.append(f"Insufficient balance. You need NGN {price} to create a child panel")
            print(f"❌ Insufficient balance: {request.user.balance} < {price}")
        
        # If no errors, create child panel
        if not errors:
            print("✅ No validation errors, creating child panel...")
            try:
                api_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
                print(f"🔑 Generated API key: {api_key[:10]}...")
                
                # Create child panel
                child_panel = ChildPanel.objects.create(
                    user=request.user,
                    domain=domain,
                    currency=currency,
                    admin_username=username,
                    password_hash=make_password(password),
                    api_key=api_key,
                    price=child_panel_price,
                    status='pending'
                )
                print(f"✅ Child panel created with ID: {child_panel.id}")
                
                # Deduct from user balance
                request.user.balance -=  Decimal(str(child_panel_price))
                request.user.save()
                print(f"💰 Balance deducted. New balance: {request.user.balance}")
                
                # Create transaction record
                transaction = Transaction.objects.create(
                    user=request.user,
                    amount=price,
                    transaction_type='child_panel_payment',
                    status='completed',
                    description=f'Payment for child panel: {domain}',
                    transaction_id=generate_transaction_id()
                )
                print(f"✅ Transaction created: {transaction.transaction_id}")
            
                # Send email notification
                try:
                    send_child_panel_creation_email(request.user.email, child_panel)
                except:
                    pass  # Email failed but panel created
                print(f"📧 Email notification would be sent to {request.user.email}")
                
                messages.success(request, f'Child panel for {domain} created successfully!')
                print("✅ Success message added, redirecting...")
                return redirect('pages:child_panel')
                
            except Exception as e:
                print(f"❌ Exception during creation: {str(e)}")
                errors.append(f"Error creating child panel: {str(e)}")
        
        # If there are errors, show them
        print(f"\n📋 Errors found: {len(errors)}")
        for i, error in enumerate(errors, 1):
            print(f"   {i}. {error}")
            messages.error(request, error)
    
    # Get user's existing child panels
    child_panels = ChildPanel.objects.filter(user=request.user).order_by('-created_at')
    print(f"\n📋 User has {child_panels.count()} existing child panels")
    
    context = {
        'page_title': page_title,
        'child_panels': child_panels,
        'currencies': currencies,
        'user': request.user,
        'selected_currency': 'NGN',  # ← ADDED DEFAULT SELECTION
        'csrf_token': request.COOKIES.get('csrftoken', ''),
    }
    
    # ========== DEBUGGING ==========
    print("\n" + "="*60)
    print("🎯 RENDERING TEMPLATE")
    print(f"📌 Template: pages/dashboard-childpanels.html")
    print(f"📌 Context keys: {list(context.keys())}")
    print(f"📌 currencies in context: {len(context['currencies'])} items")
    print(f"📌 selected_currency: {context['selected_currency']}")
    print(f"📌 child_panels count: {len(context['child_panels'])}")
    print("="*60 + "\n")
    # ================================
    
    return render(request, "pages/dashboard-childpanels.html", context)

# Helper function to validate domain
def is_valid_domain(domain):
    """Validate domain name"""
    import re
    # Simple domain validation
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return re.match(pattern, domain) is not None


# Function to send email notification
def send_child_panel_creation_email(email, child_panel):
    """Send email notification about child panel creation"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = 'Child Panel Created Successfully'
    message = f'''
    Your child panel has been created successfully!
    
    Domain: {child_panel.domain}
    Status: {child_panel.status}
    Nameservers:
    - {child_panel.nameserver1}
    - {child_panel.nameserver2}
    
    Your panel will be activated within 24 hours.
    
    Thank you for using our service!
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
def dashboard_mass_order(request):
    page_title = "Mass Order"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/dashboard-mass-order.html', context)
def dashboard_api(request):
    page_title = "API"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/dashboard-api.html', context)
@login_required(login_url='users:signin')
def dashboard_orders(request):
    user = request.user
    page_title = "Orders"
    
    # Get all orders for display
    orders = Order.objects.filter(user=user).order_by('-created_at')
    
    context = {
        'page_title': page_title,
        # Template expects these exact variable names:
        'username': user.username,
        'spent_balance': user.total_spent,
        'account_balance': user.balance,
        'order_count': user.total_orders,
        'orders': orders,
        'status': 'all',  # For the active tab
    }
    return render(request, 'pages/dashboard-orders.html', context)
def tickets(request):
    page_title = "Tickets"
    context={
        'page_title':page_title
    }
    return render(request, 'pages/dashboard-tickets.html', context)
def pending_orders(request):
    user= request.user
    orders = Order.objects.filter(user=user.id, status="Pending")
    context = {
        'orders': orders,
        'total_pending': orders.count(),
        'status': 'pending'
    }
    return render(request, 'pages/dashboard-orders.html', context)
def processing_orders(request):
    user = request.user
    orders = Order.objects.filter(user=user.id, status="Processing")
    context = {
        'orders':orders,
        'total_processing':orders.count(),
        'status':'processing'
    }
    return render(request, 'pages/dashboard-orders.html', context)
def in_progress_orders(request):
    user = request.user
    orders = Order.objects.filter(user=user.id, status="In Progress")
    context = {
        'orders': orders,
        'total_in_progress': orders.count(),
        'status': 'In Progress'
    }
    return render(request, 'pages/dashboard-orders.html', context)
def completed_orders(request):
    user = request.user
    orders = Order.objects.filter(user=user.id, status="Completed")
    context = {
        'orders':orders,
        'total_count':orders.count(),
        'status':'Completed'
    }
    return render(request, 'pages/dashboard-orders.html', context)
def cancelled_orders(request):
    user=request.user
    orders = Order.objects.filter(user=user.id, status="Cancelled")
    context = {
        'orders':orders,
        'total_count':orders.count(),
        'status':'Cancelled'
    }
    return render(request, 'pages/dashboard-orders.html', context)

def partial_orders(request):
    user=request.user
    orders = Order.objects.filter(user=user.id, status='Partially Completed')
    context = {
        'orders':orders,
        'total_count':orders.count(),
        'status':'Partially Completed'
    }
    return render(request, 'pages/dashboard-orders.html', context)

def refunded_order(request):
    user = request.user
    orders = Order.objects.filter(user=user.id, status='Refunded')
    context = {
        'orders':orders,
        'total_count':orders.count(),
        'status':'Refunded'
    }
    return render(request, 'pages/dashboard-orders.html', context)
