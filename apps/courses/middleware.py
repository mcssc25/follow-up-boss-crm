from django.conf import settings
from django.shortcuts import redirect


class SubdomainMiddleware:
    """
    Detect which subdomain the request is on and set request.portal.
    Redirect student users away from CRM paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # Strip port
        portal_subdomain = getattr(settings, 'PORTAL_SUBDOMAIN', 'courses')

        if host.startswith(f'{portal_subdomain}.'):
            request.portal = 'courses'
        else:
            request.portal = 'crm'

        # Block student users from CRM paths
        if (
            hasattr(request, 'user')
            and request.user.is_authenticated
            and getattr(request.user, 'role', '') == 'student'
            and request.portal == 'crm'
            and not request.path.startswith('/admin/')
        ):
            portal_url = getattr(settings, 'PORTAL_URL', '/')
            return redirect(portal_url)

        response = self.get_response(request)
        return response
