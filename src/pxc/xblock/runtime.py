from django.contrib.auth import get_user_model

from pxc.lib.runtime import ActivityRuntime


class XBlockActivityRuntime(ActivityRuntime):

    def get_usernames(self, ids: list[str]) -> list[tuple[str, str]]:
        User = get_user_model()
        return [(str(u.id), u.username) for u in User.objects.filter(id__in=ids).all()]
