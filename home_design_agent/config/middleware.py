"""Security headers that remain active even when admin themes alter middleware."""


class BrowserSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.setdefault('Content-Security-Policy', "frame-ancestors 'self'")
        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response
