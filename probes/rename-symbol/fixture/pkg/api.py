from .core import fetchUserData
def handler(uid):
    rec = fetchUserData(uid)
    return {"id": rec.id, "name": rec.name}
