"""Transport-neutral response values shared by HTTP route dispatchers."""


def reply(status, kind, body):
    return status, kind, body
