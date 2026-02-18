from django.urls import path
from pages import views
from pages import views2

app_name= 'pages'
urlpatterns = [
    path('instragram-followers/', views.instragram_followers, name="instragram-followers"),
    path('twitter_followers/', views.twitter_followers, name="twitter_followers"),
    path('how-to-use-really-simple-social/', views.how_tos, name='how-to-use-reallysimplesocial'),
    path('services/', views.services, name='services'),
    path('tiktok_followers', views.tiktok_followers, name='tiktok_followers'),
    path("new-order/", views.dashboard_new_order, name="new-order"),
    path('dasboard-services/',views.dashboard_services, name='dashboard_services'),
    path('order/<str:order_id>/', views2.order_detail, name='order_detail'),
    path('orders/', views.dashboard_orders, name='orders'),
    path('apis/', views.dashboard_api, name='apis'),
    path('account/', views.account, name='account'),
    path('notifications/', views.notifications, name='notifications'),
    path('change-email/', views.change_email, name='change_email'),
    path('generate-api-key/', views.generate_api_key, name='generate_api_key'),
    path('orders/', views.orders,name="orders"),
    path('add_funds/', views.dashboard_add_funds, name="add_funds"),
    path('child-panel/', views.dashboard_childpanels, name='child_panel'),
    path('notifications', views.notifications, name ="notifications"),
    path('update_notifications_set', views.update_notifications, name='update_notifications'),
    # 2FA URLs
    path('2fa/generate/', views.two_factor_generate, name='2fa_generate'),
    path('2fa/approve/', views.two_factor_approve, name='2fa_approve'),
    path('2fa/disable/', views.two_factor_disable, name='2fa_disable'),
    path('affiliates/', views.dashboard_affiliates, name='affiliates'),
    path('affiliates/referrals/', views.affiliate_referrals, name='affiliate_referrals'),
    path('affiliates/visits/', views.affiliate_visits, name='affiliate_visits'),
    path('affiliates/request-payout/', views.request_payout, name='affiliate_request_payout'),
    path('ref/<str:referral_code>/', views.referral_redirect, name='referral_redirect'),
    # Settings URLs (language, timezone, password)
    path('update-language/', views.update_language, name='update_language'),
    path('update-timezone/', views.update_timezone, name='update_timezone'),
    path('change-password/', views.change_password, name='change_password'),
    path('pending_orders/', views.pending_orders, name='pending_orders'),
    path("processing_orders/",views.processing_orders, name='proceesing_orders'),
    path('in_progress_orders/', views.in_progress_orders, name='in_progress_orders'),
    path('completed_orders/', views.completed_orders, name='completed_orders'),
    path('cancelled_orders/', views.cancelled_orders, name="cancelled_orders"),
    path('partial_orders/', views.partial_orders,name='partial_orders'),
    path('test/', views.test_view),
    path('tickets/', views2.tickets, name='tickets'),
    
    # Ticket detail - this matches your template's {% url 'ticket_detail' ticket.id %}
    path('ticket/<int:ticket_id>/', views2.ticket_detail, name='ticket_detail'),
    
    # Ticket actions
    path('ticket/<int:ticket_id>/close/', views2.close_ticket, name='close_ticket'),
    path('ticket/<int:ticket_id>/reopen/', views2.reopen_ticket, name='reopen_ticket'),
    
    # API endpoints for AJAX - these match your template's JavaScript URLs
    path('tickets/upload/', views2.ticket_upload_file, name='ticket_upload'),
    path('tickets/get-cdn-token/', views2.get_cdn_token, name='tickets_get_cdn_token'),
    
    # Alternative endpoint names your template is using:
    path('ticket/create/', views2.tickets, name='ticket_create'),  # For createTicketUrl
    path('mass_order/', views2.dashboard_mass_order, name='dashboard_mass_order'),
    
    
    # AJAX endpoint for order preview
    path('mass_order/preview/', views2.dashboard_mass_order_preview, name='mass_order_preview'),
]
