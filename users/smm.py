import requests
from django.conf import settings

class SMMApi:
    """SMM Panel API Integration"""
    
    def __init__(self):
        self.api_url = settings.SMM_API_URL  
        self.api_key = settings.SMM_API_KEY
    
    def add_order(self, service_id, link, quantity):
        """Place an order with SMM provider"""
        try:
            response = requests.post(self.api_url, data={
                'key': self.api_key,
                'action': 'add',
                'service': service_id,
                'link': link,
                'quantity': quantity
            })
            
            data = response.json()
            print(f"SMM API Response: {data}")
            return data
            
        except Exception as e:
            print(f"SMM API Error: {e}")
            return {'error': str(e)}
    
    def get_order_status(self, order_id):
        """Check status of an order"""
        try:
            response = requests.post(self.api_url, data={
                'key': self.api_key,
                'action': 'status',
                'order': order_id
            })
            
            return response.json()
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_services(self):
        """Get all available services from provider"""
        try:
            response = requests.post(self.api_url, data={
                'key': self.api_key,
                'action': 'services'
            })
            
            return response.json()
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_balance(self):
        """Get your balance with SMM provider"""
        try:
            response = requests.post(self.api_url, data={
                'key': self.api_key,
                'action': 'balance'
            })
            
            return response.json()
            
        except Exception as e:
            return {'error': str(e)}