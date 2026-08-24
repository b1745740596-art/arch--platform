from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class TalkBotSessionThrottle(UserRateThrottle):
    scope = 'talkbot_session'


class TalkBotMessageThrottle(UserRateThrottle):
    scope = 'talkbot_message'


class TalkBotConvertThrottle(UserRateThrottle):
    scope = 'talkbot_convert'


class TalkBotIPThrottle(SimpleRateThrottle):
    """A second cost fuse so many accounts cannot bypass the LLM budget per IP."""

    scope = 'talkbot_ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }
