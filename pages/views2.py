from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from users.models import Order,Service,ChildPanel
from .models import SupportTicket, TicketMessage, TicketAttachment, TicketNote
import json
import os
import re
import secrets
import string
@login_required
def tickets(request):
    """Main tickets view - list all tickets and handle creation"""
    page_title = "Tickets"
    
    # Handle ticket creation
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        errors = []
        
        # Validate
        if not subject:
            errors.append("Subject is required")
        if not message:
            errors.append("Message is required")
        
        if not errors:
            try:
                # Create ticket
                ticket = SupportTicket.objects.create(
                    user=request.user,
                    subject=subject,
                    status='open',
                    last_reply_at=timezone.now(),
                    last_reply_by=request.user
                )
                
                # Create initial message
                ticket_message = TicketMessage.objects.create(
                    ticket=ticket,
                    user=request.user,
                    message=message,
                    is_staff_reply=False
                )
                
                # Handle file attachments if any
                # You'll need to implement file upload handling here
                
                # Send notification email to admins
                send_ticket_notification_email(ticket, message)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'ticket_id': ticket.ticket_id,
                        'redirect_url': reverse('pages:ticket_detail', args=[ticket.id])
                    })
                
                messages.success(request, f'Ticket #{ticket.ticket_id} created successfully')
                return redirect('pages:ticket_detail', ticket_id=ticket.id)
                
            except Exception as e:
                errors.append(f"Error creating ticket: {str(e)}")
        
        # Handle errors
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': errors}, status=400)
        
        for error in errors:
            messages.error(request, error)
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get user's tickets
    tickets_list = SupportTicket.objects.filter(user=request.user)
    
    if search_query:
        tickets_list = tickets_list.filter(
            Q(subject__icontains=search_query) |
            Q(ticket_id__icontains=search_query) |
            Q(messages__message__icontains=search_query)
        ).distinct()
    
    # Order by most recent
    tickets_list = tickets_list.order_by('-updated_at')
    
    # Pagination
    paginator = Paginator(tickets_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': page_title,
        'tickets': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'search_query': search_query,
    }
    return render(request, 'pages/dashboard-tickets.html', context)


@login_required
def ticket_detail(request, ticket_id):
    """View and reply to a specific ticket"""
    
    # Get ticket (ensure user owns it)
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    # Handle reply
    if request.method == 'POST':
        reply_message = request.POST.get('message', '').strip()
        
        if reply_message:
            # Create reply
            ticket_message = TicketMessage.objects.create(
                ticket=ticket,
                user=request.user,
                message=reply_message,
                is_staff_reply=False
            )
            
            # Update ticket status
            ticket.status = 'customer_reply'
            ticket.last_reply_at = timezone.now()
            ticket.last_reply_by = request.user
            ticket.save()
            
            # Handle file attachments
            # Implement file upload handling here
            
            # Send notification to staff
            send_ticket_reply_notification(ticket, reply_message)
            
            messages.success(request, 'Reply sent successfully')
        else:
            messages.error(request, 'Message cannot be empty')
        
        return redirect('pages:ticket_detail', ticket_id=ticket.id)
    
    # Get messages
    messages_list = ticket.messages.all().order_by('created_at')
    
    context = {
        'page_title': f'Ticket #{ticket.ticket_id}',
        'ticket': ticket,
        'messages': messages_list,
    }
    return render(request, 'pages/ticket-detail.html', context)


@login_required
def close_ticket(request, ticket_id):
    """Close a ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    if ticket.status != 'closed':
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.save()
        
        messages.success(request, f'Ticket #{ticket.ticket_id} closed successfully')
    
    return redirect('pages:ticket_detail', ticket_id=ticket.id)


@login_required
def reopen_ticket(request, ticket_id):
    """Reopen a closed ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    if ticket.status == 'closed':
        ticket.status = 'open'
        ticket.closed_at = None
        ticket.save()
        
        messages.success(request, f'Ticket #{ticket.ticket_id} reopened successfully')
    
    return redirect('pages:ticket_detail', ticket_id=ticket.id)


@login_required
def ticket_upload_file(request):
    """Handle file upload for tickets (AJAX endpoint)"""
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        ticket_id = request.POST.get('ticket_id')
        message_id = request.POST.get('message_id')
        
        # Validate file size (5MB limit)
        if file.size > 5 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'File is too large (limit 5 MB)'
            }, status=400)
        
        # Validate file type (optional)
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 'text/plain']
        if file.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'error': 'Invalid file format'
            }, status=400)
        
        try:
            # Create attachment
            attachment = TicketAttachment.objects.create(
                ticket_id=ticket_id if ticket_id else None,
                message_id=message_id if message_id else None,
                file=file,
                file_name=file.name,
                file_size=file.size,
                uploaded_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'file_id': attachment.id,
                'file_name': attachment.file_name,
                'file_url': attachment.file.url
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)


@login_required
def get_cdn_token(request):
    """Get CDN token for file uploads"""
    import time
    import jwt
    try:
        # Generate JWT token for CDN upload
        payload = {
            'user_id': request.user.id,
            'username': request.user.username,
            'exp': int(time.time()) + 3600,  # 1 hour expiry
            'iat': int(time.time())
        }
        
        # Get secret key from settings
        secret_key = getattr(settings, 'CDN_SECRET_KEY', 'default-secret-key-change-me')
        
        # Encode token
        token = jwt.encode(payload, secret_key, algorithm='HS256')
        
        return JsonResponse({
            'success': True,
            'token': token,
            'exp': payload['exp'],
            'message': 'Token generated successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'token': '',
            'error': str(e)
        }, status=500)


# Helper functions for email notifications
def send_ticket_notification_email(ticket, message):
    """Send notification email to staff about new ticket"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = f'New Support Ticket: {ticket.ticket_id} - {ticket.subject}'
    
    message_body = f'''
    A new support ticket has been created.
    
    Ticket ID: {ticket.ticket_id}
    User: {ticket.user.username} ({ticket.user.email})
    Subject: {ticket.subject}
    
    Message:
    {message}
    
    View ticket: {settings.SITE_URL}/admin/tickets/{ticket.id}/
    '''
    
    # Send to support email
    send_mail(
        subject,
        message_body,
        settings.DEFAULT_FROM_EMAIL,
        [settings.SUPPORT_EMAIL],
        fail_silently=True,
    )


def send_ticket_reply_notification(ticket, reply_message):
    """Send notification about ticket reply"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = f'New Reply on Ticket {ticket.ticket_id}'
    
    message_body = f'''
    A new reply has been posted on ticket {ticket.ticket_id}.
    
    User: {ticket.user.username}
    Subject: {ticket.subject}
    
    Reply:
    {reply_message}
    
    View ticket: {settings.SITE_URL}/admin/tickets/{ticket.id}/
    '''
    
    send_mail(
        subject,
        message_body,
        settings.DEFAULT_FROM_EMAIL,
        [settings.SUPPORT_EMAIL],
        fail_silently=True,
    )
@login_required
def order_detail(request, order_id):
    """View single order details"""
    try:
        # Get the order - ensure it belongs to the current user
        order = Order.objects.select_related('service').get(
            order_id=order_id, 
            user=request.user
        )
        
        page_title = f"Order #{order.order_id}"
        
        context = {
            'page_title': page_title,
            'order': order,
        }
        return render(request, 'pages/order_detail.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('pages:orders')
    
@login_required
def dashboard_mass_order(request):
    """Handle mass order submissions"""
    page_title = "Mass Order"
    
    if request.method == 'POST':
        # Get the orders text from form
        orders_text = request.POST.get('MassOrderForm[orders]', '').strip()
        
        if not orders_text:
            messages.error(request, 'Please enter at least one order')
            return redirect('pages:dashboard_mass_order')
        
        # Process each line
        lines = orders_text.split('\n')
        results = {
            'success': [],
            'failed': [],
            'total_cost': Decimal('0.00'),
            'success_count': 0,
            'failed_count': 0
        }
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            
            # Parse line: service_id | link | quantity
            parts = [part.strip() for part in line.split('|')]
            
            if len(parts) != 3:
                results['failed'].append(f"Line {line_num}: Invalid format. Use: service_id | link | quantity")
                results['failed_count'] += 1
                continue
            
            service_id, link, quantity_str = parts
            
            # Validate quantity
            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except ValueError:
                results['failed'].append(f"Line {line_num}: Invalid quantity '{quantity_str}'")
                results['failed_count'] += 1
                continue
            
            # Validate link
            if not link or len(link) < 5:
                results['failed'].append(f"Line {line_num}: Invalid link")
                results['failed_count'] += 1
                continue
            
            # Check if service exists and is active
            try:
                service = Service.objects.get(id=service_id, is_active=True)
            except Service.DoesNotExist:
                results['failed'].append(f"Line {line_num}: Service ID {service_id} not found or inactive")
                results['failed_count'] += 1
                continue
            
            # Check minimum/maximum order quantity
            if quantity < service.minimum_order:
                results['failed'].append(f"Line {line_num}: Quantity {quantity} is less than minimum ({service.minimum_order}) for {service.name}")
                results['failed_count'] += 1
                continue
                
            if quantity > service.maximum_order:
                results['failed'].append(f"Line {line_num}: Quantity {quantity} exceeds maximum ({service.maximum_order}) for {service.name}")
                results['failed_count'] += 1
                continue
            
            # Calculate price
            price_per_unit = service.price_per_1000 / 1000
            total_price = Decimal(quantity) * price_per_unit
            
            # Check if user has sufficient balance
            if request.user.balance < total_price:
                results['failed'].append(f"Line {line_num}: Insufficient balance for {service.name}. Need {total_price}, have {request.user.balance}")
                results['failed_count'] += 1
                continue
            
            # Create the order
            try:
                order = Order.objects.create(
                    user=request.user,
                    service=service,
                    link=link,
                    quantity=quantity,
                    charge=total_price,
                    status='Pending',
                    order_id=generate_order_id(),
                    created_at=timezone.now()
                )
                
                # Deduct from user balance
                request.user.balance -= total_price
                request.user.total_spent += total_price
                request.user.total_orders += 1
                request.user.save()
                
                # Add to success results
                results['success'].append(f"Line {line_num}: Order #{order.order_id} created for {service.name} - {quantity} items")
                results['success_count'] += 1
                results['total_cost'] += total_price
                
            except Exception as e:
                results['failed'].append(f"Line {line_num}: Error creating order: {str(e)}")
                results['failed_count'] += 1
        
        # Save the user again to ensure balance is updated
        request.user.refresh_from_db()
        
        # Show results to user
        if results['success_count'] > 0:
            messages.success(request, f'Successfully created {results["success_count"]} orders. Total cost: ₦{results["total_cost"]}')
        
        for success_msg in results['success'][:5]:  # Show first 5 success messages
            messages.info(request, success_msg)
        
        for failed_msg in results['failed']:
            messages.error(request, failed_msg)
        
        # If it's an AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'results': results
            })
        
        return redirect('pages:dashboard_mass_order')
    
    # GET request - show the form
    context = {
        'page_title': page_title,
        'user': request.user,
        'user_balance':request.user.balance,
        'csrf_token': request.COOKIES.get('csrftoken', ''),
    }
    return render(request, 'pages/dashboard-mass-order.html', context)

def check_auth(request):
    """Check if user is authenticated (used by frontend)"""
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'balance': str(request.user.balance),
            }
        })
    else:
        return JsonResponse({
            'authenticated': False
        })

@login_required
def dashboard_mass_order_preview(request):
    """Preview mass order cost without placing order"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        orders_text = request.POST.get('orders', '').strip()
        
        if not orders_text:
            return JsonResponse({'error': 'No orders provided'}, status=400)
        
        lines = orders_text.split('\n')
        preview = {
            'valid_orders': [],
            'invalid_orders': [],
            'total_cost': Decimal('0.00'),
            'total_valid': 0,
            'total_invalid': 0
        }
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            parts = [part.strip() for part in line.split('|')]
            
            if len(parts) != 3:
                preview['invalid_orders'].append({
                    'line': line_num,
                    'error': 'Invalid format. Use: service_id | link | quantity'
                })
                preview['total_invalid'] += 1
                continue
            
            service_id, link, quantity_str = parts
            
            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except ValueError:
                preview['invalid_orders'].append({
                    'line': line_num,
                    'error': f'Invalid quantity: {quantity_str}'
                })
                preview['total_invalid'] += 1
                continue
            
            try:
                service = Service.objects.get(id=service_id, is_active=True)
            except Service.DoesNotExist:
                preview['invalid_orders'].append({
                    'line': line_num,
                    'error': f'Service ID {service_id} not found'
                })
                preview['total_invalid'] += 1
                continue
            
            if quantity < service.minimum_order:
                preview['invalid_orders'].append({
                    'line': line_num,
                    'error': f'Minimum order is {service.minimum_order} for {service.name}'
                })
                preview['total_invalid'] += 1
                continue
                
            if quantity > service.maximum_order:
                preview['invalid_orders'].append({
                    'line': line_num,
                    'error': f'Maximum order is {service.maximum_order} for {service.name}'
                })
                preview['total_invalid'] += 1
                continue
            
            price_per_unit = service.price_per_1000 / 1000
            total_price = Decimal(quantity) * price_per_unit
            
            preview['valid_orders'].append({
                'line': line_num,
                'service_id': service.id,
                'service_name': service.name,
                'link': link,
                'quantity': quantity,
                'price': float(total_price),
                'price_per_1000': float(service.price_per_1000)
            })
            preview['total_valid'] += 1
            preview['total_cost'] += total_price
        
        return JsonResponse({
            'success': True,
            'preview': preview,
            'balance': float(request.user.balance),
            'has_sufficient_balance': request.user.balance >= preview['total_cost']
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


def generate_order_id():
    """Generate unique order ID"""
    import random
    import string
    import time
    
    timestamp = int(time.time())
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    